"""Thin clients for the watsonx.data pieces the pipeline uses.

- IBM Cloud IAM token (cached until shortly before it expires)
- Cloud Object Storage: upload and list objects in the watsonx.data bucket
- Spark engine: submit a PySpark application and wait for it
- Presto engine: run SQL with the standard Presto Python client
- Engines: status, pause and resume (the Lite plan bills idle engines)
"""

from __future__ import annotations

import base64
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import prestodb
import requests

from .config import Settings

IAM_URL = "https://iam.cloud.ibm.com/identity/token"


class WatsonxData:
    def __init__(self, s: Settings):
        self.s = s
        self._token: str | None = None
        self._token_exp = 0.0

    # ------------------------------------------------------------------ auth
    def token(self) -> str:
        if not self._token or time.time() > self._token_exp - 300:
            r = requests.post(
                IAM_URL,
                data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self.s.api_key},
                timeout=30,
            )
            r.raise_for_status()
            body = r.json()
            self._token, self._token_exp = body["access_token"], float(body["expiration"])
        return self._token

    def _api(self, method: str, path: str, **kw) -> requests.Response:
        headers = {"Authorization": f"Bearer {self.token()}", "AuthInstanceId": self.s.wxd_crn}
        r = requests.request(method, f"{self.s.wxd_host}/lakehouse/api/v3{path}", headers=headers, timeout=60, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
        return r

    # ------------------------------------------------------------------- COS
    def upload(self, local: Path, key: str, bucket: str | None = None) -> None:
        url = f"{self.s.cos_endpoint}/{bucket or self.s.landing_bucket}/{key}"
        with open(local, "rb") as f:
            r = requests.put(url, data=f, headers={"Authorization": f"Bearer {self.token()}"}, timeout=120)
        r.raise_for_status()

    def list_objects(self, prefix: str, bucket: str | None = None) -> list[tuple[str, int]]:
        out, token = [], None
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        while True:
            params = {"list-type": "2", "prefix": prefix}
            if token:
                params["continuation-token"] = token
            r = requests.get(f"{self.s.cos_endpoint}/{bucket or self.s.bucket}", params=params,
                             headers={"Authorization": f"Bearer {self.token()}"}, timeout=60)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            for c in root.findall("s3:Contents", ns):
                out.append((c.find("s3:Key", ns).text, int(c.find("s3:Size", ns).text)))
            nxt = root.find("s3:NextContinuationToken", ns)
            if nxt is None:
                return out
            token = nxt.text

    def read_object(self, key: str, bucket: str | None = None) -> str:
        r = requests.get(f"{self.s.cos_endpoint}/{bucket or self.s.landing_bucket}/{key}",
                         headers={"Authorization": f"Bearer {self.token()}"}, timeout=60)
        r.raise_for_status()
        return r.text

    # ----------------------------------------------------------------- Spark
    def submit_spark(self, app_key: str, args: list[str], name: str, conf: dict | None = None,
                     packages: str | None = None, env: dict | None = None) -> str:
        lb = self.s.landing_bucket
        if not (lb and self.s.landing_access_key and self.s.landing_secret_key):
            raise SystemExit("Set LANDING_BUCKET and its HMAC keys in .env before running Spark jobs")
        details = {
            "application": f"s3a://{lb}/{app_key}",
            "arguments": args,
            "name": name,
            "conf": {
                "spark.driver.memory": "4G",
                "spark.executor.memory": "4G",
                "spark.driver.cores": "1",
                "spark.executor.cores": "1",
                "ae.spark.executor.count": "1",
                # Lets the watsonx.data credential provider sign object-storage requests
                # (reading the application, landing files and the Iceberg warehouse).
                "spark.hadoop.wxd.apiKey": "Basic " + base64.b64encode(
                    f"{self.s.wxd_user}:{self.s.api_key}".encode()).decode(),
                # The landing bucket (raw files and application code) is read with HMAC keys.
                f"spark.hadoop.fs.s3a.bucket.{lb}.endpoint": self.s.cos_direct_endpoint,
                f"spark.hadoop.fs.s3a.bucket.{lb}.access.key": self.s.landing_access_key,
                f"spark.hadoop.fs.s3a.bucket.{lb}.secret.key": self.s.landing_secret_key,
                f"spark.hadoop.fs.s3a.bucket.{lb}.aws.credentials.provider":
                    "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
                **self._hmac_conf(self.s.bucket),
                **(conf or {}),
            },
        }
        if packages:
            details["packages"] = packages
        if env:
            details["env"] = env
        r = self._api("POST", f"/spark_engines/{self.s.spark_engine}/applications",
                      json={"application_details": details})
        return r.json()["id"]

    def _hmac_conf(self, bucket: str) -> dict:
        """Use the HMAC keys (instead of the watsonx.data signer) for the Iceberg warehouse bucket."""
        p = f"spark.hadoop.fs.s3a.bucket.{bucket}"
        return {
            f"{p}.endpoint": self.s.cos_direct_endpoint,
            f"{p}.access.key": self.s.landing_access_key,
            f"{p}.secret.key": self.s.landing_secret_key,
            f"{p}.aws.credentials.provider": "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
            f"{p}.custom.signers": "",
            f"{p}.s3.signing-algorithm": "AWSS3V4SignerType",
        }

    def spark_state(self, app_id: str) -> dict:
        return self._api("GET", f"/spark_engines/{self.s.spark_engine}/applications/{app_id}").json()

    def wait_spark(self, app_id: str, poll: int = 10, timeout: int = 1800) -> dict:
        start, last = time.time(), None
        while time.time() - start < timeout:
            st = self.spark_state(app_id)
            state = st.get("state")
            if state != last:
                print(f"  [{int(time.time() - start):>4}s] {app_id}: {state}", flush=True)
                last = state
            if state in ("finished", "failed", "stopped", "killed", "error"):
                return st
            time.sleep(poll)
        raise TimeoutError(f"Spark application {app_id} still running after {timeout}s")

    # ---------------------------------------------------------------- Presto
    def presto(self, catalog: str | None = None, schema: str | None = None):
        return prestodb.dbapi.connect(
            host=self.s.presto_host, port=443, http_scheme="https",
            user=self.s.wxd_user, catalog=catalog or self.s.catalog, schema=schema or "default",
            auth=prestodb.auth.BasicAuthentication(self.s.wxd_user, self.s.api_key),
            request_timeout=600,
        )

    def sql(self, statement: str, catalog: str | None = None) -> tuple[list[str], list[tuple]]:
        cur = self.presto(catalog).cursor()
        cur.execute(statement)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, rows

    # --------------------------------------------------------------- engines
    def engines(self) -> list[dict]:
        presto = self._api("GET", "/presto_engines").json().get("presto_engines", [])
        spark = self._api("GET", "/spark_engines").json().get("spark_engines", [])
        return [{"id": e["id"], "type": "presto", "status": e["status"]} for e in presto] + \
               [{"id": e["id"], "type": "spark", "status": e["status"]} for e in spark]

    def set_engine(self, engine_type: str, engine_id: str, action: str) -> None:
        self._api("POST", f"/{engine_type}_engines/{engine_id}/{action}", json={})

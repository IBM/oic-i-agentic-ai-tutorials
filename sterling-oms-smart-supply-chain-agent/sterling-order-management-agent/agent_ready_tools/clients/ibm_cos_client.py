import base64
from typing import Any, Dict, List, Optional

import ibm_boto3  # from ibm-cos-sdk
from ibm_botocore.client import Config
from ibm_botocore.exceptions import ClientError

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class IBMCOSClient:
    """A remote client for IBM Cloud Object Storage."""

    def __init__(
        self,
        api_key: str,
        instance_id: str,
        endpoint_url: str,
    ):
        """
        Initializes the IBM COS client using IAM-based authentication.

        Args:
            api_key: The API key for IBM COS.
            instance_id: The service instance ID (CRN) for IBM COS.
            endpoint_url: The regional endpoint URL for the COS instance.
        """
        self.api_key = api_key
        self.instance_id = instance_id
        self.endpoint_url = endpoint_url

        self.cos_resource = ibm_boto3.resource(
            "s3",
            ibm_api_key_id=self.api_key,
            ibm_service_instance_id=self.instance_id,
            config=Config(signature_version="oauth"),
            endpoint_url=self.endpoint_url,
        )

    def list_buckets(self) -> List[Dict[str, Any]]:
        """
        Lists all buckets in the IBM COS instance.

        Returns:
            A list of dictionaries, where each dictionary contains information about a bucket,
            or a list with a single error dictionary on failure.
        """
        try:
            return [
                {"name": bucket.name, "creation_date": bucket.creation_date.isoformat()}
                for bucket in self.cos_resource.buckets.all()
            ]
        except ClientError as e:
            return [{"status": "error", "message": e.response["Error"]["Message"]}]

    def list_objects(self, bucket_name: str, prefix: Optional[str] = "") -> List[Dict[str, Any]]:
        """
        Lists all objects in a specific bucket, optionally filtered by a prefix.

        Args:
            bucket_name: The name of the bucket.
            prefix: An optional prefix to filter objects by.

        Returns:
            A list of dictionaries, where each dictionary contains information about an object,
            or a list with a single error dictionary on failure.
        """
        try:
            bucket = self.cos_resource.Bucket(bucket_name)
            return [
                {
                    "key": obj.key,
                    "last_modified": obj.last_modified.isoformat(),
                    "size": obj.size,
                    "storage_class": obj.storage_class,
                }
                for obj in bucket.objects.filter(Prefix=prefix)
            ]
        except ClientError as e:
            return [{"status": "error", "message": e.response["Error"]["Message"]}]

    def delete_object(self, bucket_name: str, object_key: str) -> Dict[str, Any]:
        """
        Deletes an object from a bucket.

        Args:
            bucket_name: The name of the bucket.
            object_key: The key of the object to delete.

        Returns:
            A dictionary with a success message or an error.
        """
        try:
            self.cos_resource.Object(bucket_name, object_key).delete()
            return {
                "status": "success",
                "message": f"Object '{object_key}' deleted from bucket '{bucket_name}'.",
            }
        except ClientError as e:
            return {"status": "error", "message": e.response["Error"]["Message"]}

    def create_object(self, bucket_name: str, object_key: str, content: str) -> Dict[str, Any]:
        """
        Creates an object in a bucket.

        Args:
            bucket_name: The name of the bucket.
            object_key: The key (name) of the object to create.
            content: The file to be added to the object.

        Returns:
            A dictionary with a success message or an error.
        """
        try:
            decoded_bytes = base64.b64decode(content)
            self.cos_resource.Object(bucket_name, object_key).put(Body=decoded_bytes)
            return {
                "status": "success",
                "message": f"Object '{object_key}' created successfully in bucket '{bucket_name}'.",
            }
        except ClientError as e:
            return {"status": "error", "message": e.response["Error"]["Message"]}

    def copy_object(
        self, source_bucket: str, source_key: str, destination_bucket: str, destination_key: str
    ) -> Dict[str, Any]:
        """
        Copies an object from one bucket to another.

        Args:
            source_bucket: The name of the source bucket.
            source_key: The key of the source object.
            destination_bucket: The name of the destination bucket.
            destination_key: The key for the copied object.

        Returns:
            A dictionary with a success message or an error.
        """
        try:
            copy_source = {"Bucket": source_bucket, "TargetKey": source_key}

            self.cos_resource.Object(destination_bucket, destination_key).copy(copy_source)

            return {
                "status": "success",
                "message": f"Object '{source_key}' copied from '{source_bucket}' to '{destination_key}' in '{destination_bucket}'.",
            }

        except ClientError as e:
            return {"status": "error", "message": e.response["Error"]["Message"]}

    def download_object(self, bucket_name: str, object_key: str) -> Dict[str, Any]:
        """
        Downloads an object from a bucket.

        Args:
            bucket_name: The name of the bucket.
            object_key: The key of the object to download.

        Returns:
            A dictionary containing the status, message, and content of the object.
        """
        try:
            response = self.cos_resource.Object(bucket_name, object_key).get()
            content = response["Body"].read()

            return {
                "status": "success",
                "message": f"Object '{object_key}' downloaded from bucket '{bucket_name}'.",
                "content": content,
            }
        except ClientError as e:
            return {"status": "error", "message": e.response["Error"]["Message"]}

    def list_object_details(self, bucket_name: str, object_key: str) -> Dict[str, Any]:
        """
        Retrieves metadata of a specific object from IBM COS.

        Args:
            bucket_name: The name of the bucket.
            object_key: The key of the object.

        Returns:
            A dictionary with object metadata or an error.
        """
        try:
            obj = self.cos_resource.Object(bucket_name, object_key)
            obj.load()

            return {
                "key": object_key,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                "etag": obj.e_tag,
                "size": obj.content_length,
                "content_type": obj.content_type,
                "cache_control": obj.cache_control,
                "accept_ranges": obj.accept_ranges,
            }

        except ClientError as e:
            return {"status": "error", "message": e.response["Error"]["Message"]}


def get_ibm_cos_client() -> IBMCOSClient:
    """
    Get the IBM COS client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the IBMCOSClient.
    """
    credentials = get_tool_credentials(Systems.IBM_COS)
    ibm_cos_client = IBMCOSClient(
        api_key=credentials[CredentialKeys.API_KEY],
        instance_id=credentials[CredentialKeys.INSTANCE_ID],
        endpoint_url=credentials[CredentialKeys.BASE_URL],
    )
    return ibm_cos_client

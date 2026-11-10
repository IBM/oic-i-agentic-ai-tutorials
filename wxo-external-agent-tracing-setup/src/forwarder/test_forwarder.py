"""
forwarder/test_forwarder.py
===========================
Unit tests for the OTLP Trace Forwarder.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from forwarder.forwarder import (
    OtlpForwarder, build_otlp_payload, count_tokens, decode_otlp_protobuf,
    post_scores_to_wxo,
)
from forwarder.lambda_function import lambda_handler


class TestOtlpForwarder(unittest.TestCase):

    def setUp(self):
        self.agent_map = {
            "default": {
                "wxo_agent_id": "default-uuid-1111",
                "wxo_display_name": "Default Agent",
            },
            "support_bot": {
                "wxo_agent_id": "support-uuid-2222",
                "wxo_display_name": "Customer Support Bot",
            },
            "claude-3-7-sonnet": {
                "wxo_agent_id": "claude-uuid-3333",
                "wxo_tenant_id": "tenant-override-123",
            },
        }
        self.forwarder = OtlpForwarder(
            agent_map=self.agent_map,
            default_tenant_id="global-tenant",
            default_export_url="https://api.test/traces",
            default_api_key="test-api-key",
        )

    def test_token_counter(self):
        self.assertEqual(count_tokens("Hello world!"), 3)
        self.assertEqual(count_tokens(""), 0)

    def test_agent_resolution_exact_key(self):
        routing = self.forwarder.resolve_wxo_agent(["support_bot"])
        self.assertEqual(routing["agent_id"], "support-uuid-2222")
        self.assertEqual(routing["display_name"], "Customer Support Bot")
        self.assertEqual(routing["tenant_id"], "global-tenant")

    def test_agent_resolution_per_entry_override(self):
        routing = self.forwarder.resolve_wxo_agent(["claude-3-7-sonnet"])
        self.assertEqual(routing["agent_id"], "claude-uuid-3333")
        self.assertEqual(routing["tenant_id"], "tenant-override-123")

    def test_agent_resolution_direct_uuid(self):
        direct_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        routing = self.forwarder.resolve_wxo_agent([direct_uuid])
        self.assertEqual(routing["agent_id"], direct_uuid)

    def test_agent_resolution_default_fallback(self):
        routing = self.forwarder.resolve_wxo_agent(["unknown-agent"])
        self.assertEqual(routing["agent_id"], "default-uuid-1111")

    def test_build_otlp_payload_root_and_tools(self):
        payload = build_otlp_payload(
            agent_id="test-id",
            agent_name="my_agent",
            tenant_id="my-tenant",
            prompt="Find order status",
            response="Order #1234 is shipped",
            start_ns=1000,
            end_ns=2000,
            tool_calls=[{
                "name": "lookup_order",
                "input": '{"order_id": "1234"}',
                "output": '{"status": "shipped"}',
                "start_ns": 1100,
                "end_ns": 1500,
                "is_error": False,
            }],
        )

        self.assertIn("resourceSpans", payload)
        rs = payload["resourceSpans"][0]
        spans = rs["scopeSpans"][0]["spans"]
        self.assertEqual(len(spans), 5)
        root = spans[0]
        tool = spans[3]

        self.assertEqual(root["name"], "invoke_agent my_agent")
        self.assertEqual(tool["name"], "lookup_order")
        self.assertEqual(tool["parentSpanId"], spans[2]["spanId"])

    def test_build_otlp_payload_input_envelope(self):
        """Root span must carry gen_ai.message.input as the WXO structured
        message envelope object, not a bare prompt string."""
        payload = build_otlp_payload(
            agent_id="test-id",
            agent_name="my_agent",
            tenant_id="my-tenant",
            prompt="What is the weather?",
            response="It is sunny.",
            session_id="sess-abc",
        )
        root_attrs = {
            a["key"]: a["value"]
            for a in payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"]
        }
        self.assertIn("gen_ai.message.input", root_attrs)
        envelope = json.loads(root_attrs["gen_ai.message.input"]["stringValue"])
        self.assertEqual(envelope["role"], "user")
        self.assertEqual(envelope["content"], "What is the weather?")
        self.assertEqual(envelope["session_id"], "sess-abc")
        self.assertIsNone(envelope["trace_id"])
        self.assertIn("additional_properties", envelope)
        self.assertFalse(envelope["additional_properties"]["a2a_task_completed"])

    def test_build_otlp_payload_reasoning_steps(self):
        """Reasoning steps must appear as gen_ai.reasoning events on the root
        span, matching the Langfuse steps shape WXO's internal pipeline emits."""
        payload = build_otlp_payload(
            agent_id="test-id",
            agent_name="my_agent",
            tenant_id="my-tenant",
            prompt="Explain quantum entanglement.",
            response="Entanglement is ...",
            reasoning_steps=["First, consider the wave function.", "Then apply Bell's theorem."],
        )
        root_span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertIn("events", root_span)
        events = root_span["events"]
        self.assertEqual(len(events), 2)
        e_attrs_0 = {a["key"]: a["value"]["stringValue"] for a in events[0]["attributes"]}
        self.assertEqual(events[0]["name"], "gen_ai.reasoning")
        self.assertEqual(e_attrs_0["gen_ai.reasoning.content"], "First, consider the wave function.")
        self.assertEqual(e_attrs_0["langfuse.step.type"], "reasoning")
        self.assertIn("generate_content", e_attrs_0["langfuse.step.name"])

    def test_build_otlp_payload_no_reasoning_steps_no_events(self):
        """When no reasoning_steps are provided, the root span must not have
        an events key (keeps the wire payload minimal)."""
        payload = build_otlp_payload(
            agent_id="test-id",
            agent_name="my_agent",
            tenant_id="my-tenant",
            prompt="Hello",
            response="Hi",
        )
        root_span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertNotIn("events", root_span)

    def test_process_payload_extracts_reasoning_from_span_event(self):
        """Reasoning events in the incoming OTLP span must be collected and
        forwarded as gen_ai.reasoning events on the outgoing root span."""
        captured = []

        def fake_build(**kw):
            captured.append(kw.get("reasoning_steps"))
            # Return a minimal valid payload so the forwarder doesn't crash
            return {
                "resourceSpans": [{
                    "resource": {"attributes": []},
                    "scopeSpans": [{"scope": {}, "spans": []}],
                }]
            }

        sample_otlp = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "default"}},
                ]},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": "aabbccdd",
                        "spanId": "deadbeef",
                        "name": "invoke_agent",
                        "startTimeUnixNano": 1_000_000_000,
                        "endTimeUnixNano":   2_000_000_000,
                        "attributes": [],
                        "events": [
                            {
                                "name": "gen_ai.reasoning",
                                "timeUnixNano": 1_100_000_000,
                                "attributes": [
                                    {"key": "gen_ai.reasoning.content",
                                     "value": {"stringValue": "I should check the docs first."}},
                                ],
                            }
                        ],
                    }]
                }]
            }]
        }

        with patch("forwarder.forwarder.build_otlp_payload", side_effect=fake_build), \
             patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo", return_value="J"):
            self.forwarder.process_payload(
                body_bytes=json.dumps(sample_otlp).encode(),
                content_type="application/json",
            )

        self.assertEqual(len(captured), 1)
        self.assertIsNotNone(captured[0])
        self.assertIn("I should check the docs first.", captured[0])

    @patch("forwarder.forwarder.urlopen")
    def test_process_payload_json(self, mock_urlopen):
        # Mock IAM Token response and WXO ingest response
        mock_resp_iam = MagicMock()
        mock_resp_iam.read.return_value = json.dumps({"token": "mock-token", "expires_in": 3600}).encode()
        mock_resp_iam.__enter__.return_value = mock_resp_iam

        mock_resp_wxo = MagicMock()
        mock_resp_wxo.status = 200
        mock_resp_wxo.read.return_value = json.dumps({"data": {"id": "JOB-12345"}}).encode()
        mock_resp_wxo.__enter__.return_value = mock_resp_wxo

        mock_urlopen.side_effect = [mock_resp_iam, mock_resp_wxo]

        sample_otlp = {
            "resourceSpans": [{
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "support_bot"}}]},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": "11112222333344445555666677778888",
                        "spanId": "1234567812345678",
                        "name": "invoke_agent",
                        "startTimeUnixNano": 1000000,
                        "endTimeUnixNano": 2000000,
                        "attributes": [
                            {"key": "gen_ai.prompt", "value": {"stringValue": "Help me reset password"}},
                            {"key": "gen_ai.completion", "value": {"stringValue": "Follow the link sent to your email"}},
                        ],
                    }]
                }]
            }]
        }

        job_ids = self.forwarder.process_payload(
            body_bytes=json.dumps(sample_otlp).encode(),
            content_type="application/json",
        )
        self.assertEqual(job_ids, ["JOB-12345"])

    def test_unmapped_agent_is_not_routed_to_first_entry(self):
        del self.forwarder.agent_map["default"]  # no default => unmapped agents must resolve to nothing
        routing = self.forwarder.resolve_wxo_agent(["harness_unknown-XXXX"])
        self.assertEqual(routing["agent_id"], "")


    def test_aws_runtime_id_routes_to_mapped_wxo_agent(self):
        self.forwarder.agent_map["harness_wxoTracingTest-DEqjmm77sf"] = {"wxo_agent_id": "wxo-y-uuid"}
        sample = {"resourceSpans": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "support_bot"}},  # would match a different entry
                {"key": "aws.agent.runtime.id", "value": {"stringValue": "harness_wxoTracingTest-DEqjmm77sf"}},
            ]},
            "scopeSpans": [{"spans": [{"spanId": "1234567812345678", "name": "invoke_agent"}]}],
        }]}
        with patch.object(self.forwarder, "resolve_wxo_agent", wraps=self.forwarder.resolve_wxo_agent) as spy, \
             patch("forwarder.forwarder.get_bearer_token", return_value=""):
            self.forwarder.process_payload(json.dumps(sample).encode())
        keys = spy.call_args.kwargs["candidate_keys"]
        self.assertEqual(self.forwarder.resolve_wxo_agent(keys)["agent_id"], "wxo-y-uuid")


    def test_explicit_agent_hint_from_path_header_and_query(self):
        body = json.dumps({"resourceSpans": [{"resource": {"attributes": []},
                           "scopeSpans": [{"spans": [{"spanId": "a", "name": "n"}]}]}]}).encode()
        seen = []

        def fake_resolve(candidate_keys=None, default_name=""):
            seen.append(candidate_keys[0])
            return {"agent_id": "", "agent_name": "x", "tenant_id": "", "export_url": "",
                    "api_key": "", "token_url": "", "environment": ""}

        with patch.object(self.forwarder, "resolve_wxo_agent", side_effect=fake_resolve):
            self.forwarder.process_payload(body, path_agent_id="from-path")
            self.forwarder.process_payload(body, headers={"x-wxo-agent-id": "from-header"})
            self.forwarder.process_payload(body, query_params={"agent_id": ["from-query"]})
        self.assertEqual(seen, ["from-path", "from-header", "from-query"])


    def test_auth_token(self):
        self.assertTrue(self.forwarder.is_authorized({}))  # no token configured = open
        self.forwarder.auth_token = "s3cret"
        self.assertTrue(self.forwarder.is_authorized({"Authorization": "Bearer s3cret"}))
        self.assertTrue(self.forwarder.is_authorized({"X-Api-Key": "s3cret"}))
        self.assertFalse(self.forwarder.is_authorized({"Authorization": "Bearer wrong"}))
        self.assertFalse(self.forwarder.is_authorized({}))

    def test_handle_auth_off_by_default(self):
        """No token configured: requests are processed without any auth check."""
        with patch.object(OtlpForwarder, "refresh"), \
             patch.object(OtlpForwarder, "process_payload", return_value=["job-1"]):
            status, body = self.forwarder.handle(b"{}", headers={})
        self.assertEqual((status, body), (200, {"status": "ok", "job_ids": ["job-1"]}))

    def test_handle_auth_on(self):
        """Token configured: wrong/missing -> 401 and nothing is processed; right token -> 200."""
        self.forwarder.auth_token = "s3cret"
        with patch.object(OtlpForwarder, "refresh"), \
             patch.object(OtlpForwarder, "process_payload", return_value=["job-1"]) as proc:
            self.assertEqual(self.forwarder.handle(b"{}", headers={})[0], 401)
            self.assertEqual(self.forwarder.handle(b"{}", headers={"authorization": "Bearer nope"})[0], 401)
            proc.assert_not_called()
            self.assertEqual(self.forwarder.handle(b"{}", headers={"authorization": "Bearer s3cret"})[0], 200)
            self.assertEqual(self.forwarder.handle(b"{}", headers={"x-api-key": "s3cret"})[0], 200)

    def test_handle_returns_500_on_error(self):
        with patch.object(OtlpForwarder, "refresh"), \
             patch.object(OtlpForwarder, "process_payload", side_effect=RuntimeError("boom")):
            status, body = self.forwarder.handle(b"{}")
        self.assertEqual(status, 500)
        self.assertIn("boom", body["error"])

    def test_handle_refreshes_before_processing(self):
        calls = []
        with patch.object(OtlpForwarder, "refresh", side_effect=lambda: calls.append("refresh")), \
             patch.object(OtlpForwarder, "process_payload", side_effect=lambda **k: calls.append("process") or []):
            self.forwarder.handle(b"{}")
        self.assertEqual(calls, ["refresh", "process"])

    def test_lambda_handler_rejects_missing_token(self):
        from forwarder import lambda_function
        with patch.object(lambda_function.forwarder, "refresh"), \
             patch.object(lambda_function.forwarder, "auth_token", "s3cret"):
            res = lambda_handler({"rawPath": "/v1/traces", "body": "{}"}, None)
        self.assertEqual(res["statusCode"], 401)

    def test_refresh_applies_settings(self):
        settings = {"tenant_id": "t-new", "otel_export_url": "https://new/traces",
                    "environment": "live"}
        with patch.object(OtlpForwarder, "get_settings", return_value=settings), \
             patch.object(OtlpForwarder, "get_agent_map", return_value={"a": {"wxo_agent_id": "x"}}):
            self.forwarder.refresh()
        self.assertEqual(self.forwarder.default_tenant_id, "t-new")
        self.assertEqual(self.forwarder.default_environment, "live")
        self.assertIn("a", self.forwarder.agent_map)

    def test_lambda_handler_health(self):
        res = lambda_handler({"rawPath": "/health"}, None)
        self.assertEqual(res["statusCode"], 200)
        body = json.loads(res["body"])
        self.assertEqual(body["status"], "healthy")

    def test_sql_mapping_loading(self):
        import sqlite3
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = sqlite3.connect(tmp.name)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE wxo_agent_mappings (
                    agent_name VARCHAR(255) PRIMARY KEY,
                    wxo_agent_id VARCHAR(255) NOT NULL,
                    wxo_tenant_id VARCHAR(255),
                    wxo_otel_export_url TEXT,
                    wxo_display_name VARCHAR(255),
                    environment VARCHAR(50)
                );
            """)
            cur.execute("""
                INSERT INTO wxo_agent_mappings VALUES (
                    'sql-bot', 'sql-uuid-999', 'tenant-sql', 'https://api.test/sql/traces', 'SQL Bot', 'live'
                );
            """)
            conn.commit()
            conn.close()

            res = OtlpForwarder._load_from_sql(f"sqlite:///{tmp.name}")
            self.assertIn("sql-bot", res)
            self.assertEqual(res["sql-bot"]["wxo_agent_id"], "sql-uuid-999")
            self.assertEqual(res["sql-bot"]["wxo_tenant_id"], "tenant-sql")


    def _make_anthropic_otlp(self, trace_id, session_turn_span_id,
                             model_request_span_id, input_tokens, output_tokens):
        """Build two-span Anthropic OTLP payloads (one span each, as the OTel
        collector sends them — separate HTTP requests)."""
        model_req_batch = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "claude-platform"}}
                ]},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": trace_id,
                        "spanId": model_request_span_id,
                        "parentSpanId": session_turn_span_id,
                        "name": "anthropic.model_request",
                        "startTimeUnixNano": 1100000,
                        "endTimeUnixNano": 1900000,
                        "attributes": [
                            {"key": "gen_ai.request.model",       "value": {"stringValue": "claude-opus-5-5"}},
                            {"key": "gen_ai.usage.input_tokens",  "value": {"intValue": input_tokens}},
                            {"key": "gen_ai.usage.output_tokens", "value": {"intValue": output_tokens}},
                            {"key": "gen_ai.provider.name",       "value": {"stringValue": "anthropic"}},
                            {"key": "gen_ai.operation.name",      "value": {"stringValue": "chat"}},
                        ],
                    }]
                }]
            }]
        }
        session_turn_batch = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "claude-platform"}}
                ]},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": trace_id,
                        "spanId": session_turn_span_id,
                        "parentSpanId": "733c9f7b452b3eee",  # parent outside this payload
                        "name": "anthropic.session.turn",
                        "startTimeUnixNano": 1000000,
                        "endTimeUnixNano": 2000000,
                        "attributes": [
                            {"key": "gen_ai.agent.id",        "value": {"stringValue": "default"}},
                            {"key": "gen_ai.agent.name",      "value": {"stringValue": "TestAgent"}},
                            {"key": "gen_ai.provider.name",   "value": {"stringValue": "anthropic"}},
                            {"key": "gen_ai.operation.name",  "value": {"stringValue": "invoke_agent"}},
                            {"key": "anthropic.session.id",   "value": {"stringValue": "sesn_test"}},
                            {"key": "gen_ai.input.messages",  "value": {"stringValue": '[{"role":"user","parts":[{"type":"text","content":"hello"}]}]'}},
                            {"key": "gen_ai.output.messages", "value": {"stringValue": '[{"role":"assistant","parts":[{"type":"text","content":"Hi!"}]}]'}},
                        ],
                    }]
                }]
            }]
        }
        return model_req_batch, session_turn_batch

    def test_anthropic_session_turn_no_token_doubling(self):
        """Each Anthropic span arrives in its own HTTP request (one span per batch).
        anthropic.model_request must never produce a WXO trace; its tokens must be
        picked up by the subsequent anthropic.session.turn — no doubling."""
        trace_id = "fc361a0b48bb2825706d381595101e0d"
        session_turn_span_id = "7ab545c4abf700a5"
        model_request_span_id = "ca5ffc8bb87c604c"

        model_req_batch, session_turn_batch = self._make_anthropic_otlp(
            trace_id, session_turn_span_id, model_request_span_id,
            input_tokens=6679, output_tokens=843,
        )

        calls = []

        def fake_post(payload, bearer_token, export_url, agent_id, tenant_id, logger=None):
            calls.append(payload)
            return "JOB-TEST"

        with patch("forwarder.forwarder.get_bearer_token", return_value="mock-token"), \
             patch("forwarder.forwarder.post_to_wxo", side_effect=fake_post):
            # Simulate two separate HTTP requests, as the OTel collector sends them
            ids1 = self.forwarder.process_payload(
                body_bytes=json.dumps(model_req_batch).encode(),
                content_type="application/json",
            )
            ids2 = self.forwarder.process_payload(
                body_bytes=json.dumps(session_turn_batch).encode(),
                content_type="application/json",
            )

        # model_request must produce no WXO trace
        self.assertEqual(ids1, [], "anthropic.model_request must not be forwarded")
        # session.turn must produce exactly one WXO trace
        self.assertEqual(len(ids2), 1, "Expected exactly one forwarded trace from session.turn")
        self.assertEqual(len(calls), 1, "post_to_wxo must be called exactly once total")

        # Token counts must not be doubled
        fwd_spans = calls[0]["resourceSpans"][0]["scopeSpans"][0]["spans"]
        root_span = fwd_spans[0]
        attrs = {a["key"]: (a["value"].get("intValue") or a["value"].get("stringValue") or 0)
                 for a in root_span.get("attributes", [])}
        self.assertEqual(attrs.get("gen_ai.usage.input_tokens"), 6679)
        self.assertEqual(attrs.get("gen_ai.usage.output_tokens"), 843)

    def test_anthropic_model_request_alone_never_forwarded(self):
        """anthropic.model_request arriving with no prior session.turn in the same
        payload must never be forwarded as a WXO trace on its own."""
        trace_id = "aabbccddeeff00112233445566778899"
        model_req_batch, _ = self._make_anthropic_otlp(
            trace_id, "parentXXX", "childYYY",
            input_tokens=100, output_tokens=50,
        )

        calls = []
        with patch("forwarder.forwarder.get_bearer_token", return_value="mock-token"), \
             patch("forwarder.forwarder.post_to_wxo", side_effect=lambda **kw: calls.append(kw) or "J"):
            ids = self.forwarder.process_payload(
                body_bytes=json.dumps(model_req_batch).encode(),
                content_type="application/json",
            )

        self.assertEqual(ids, [], "anthropic.model_request must never be forwarded standalone")
        self.assertEqual(calls, [])


    # ------------------------------------------------------------------ AWS --

    def _make_aws_strands_payload(self):
        """Minimal AWS Strands flat-format OTLP payload matching real span shape."""
        return {
            "resource_attrs": {
                "telemetry.sdk.language": "python",
                "telemetry.sdk.name": "opentelemetry",
                "telemetry.sdk.version": "1.44.0",
                "aws.agent.runtime.id": "harness_wxoTracingTest-DEqjmm77sf",
                "wxo.agent.id": "61e315a1-0749-49fc-9972-fd92068fd881",
                "wxo.agent.name": "wxo_tracing_test",
                "wxo.environment": "draft",
                "service.name": "wxo_tracing_test",
            },
            "scope_spans": [
                {
                    "scope_name": "strands.telemetry.tracer",
                    "spans": [
                        {
                            # subordinate — must not be forwarded
                            "name": "execute_event_loop_cycle",
                            "traceId": "6ad3aee9244cc512487ba36768b48bc2",
                            "spanId": "a949ff33a7d2fca0",
                            "parentSpanId": "364f93fb93e0d393",
                            "startTimeUnixNano": 1792257802186443184,
                            "endTimeUnixNano": 1792257802934339104,
                            "attributes": {},
                            "events": [],
                        },
                        {
                            # top-level invocation — must be forwarded
                            "name": "invoke_agent Strands Agents",
                            "traceId": "6ad3aee9244cc512487ba36768b48bc2",
                            "spanId": "364f93fb93e0d393",
                            "parentSpanId": "1116434f34966702",
                            "startTimeUnixNano": 1792257801921408925,
                            "endTimeUnixNano": 1792257802934589978,
                            "attributes": {
                                "harness.id": "wxoTracingTest-EQnaAkefWw",
                                "session.id": "79ed61d4-63a5-4b3c-a777-1313f1081baf",
                                "gen_ai.operation.name": "invoke_agent",
                                "gen_ai.system": "strands-agents",
                                "gen_ai.agent.name": "Strands Agents",
                                "gen_ai.request.model": "us.amazon.nova-lite-v1:0",
                                "gen_ai.usage.input_tokens": 789,
                                "gen_ai.usage.output_tokens": 43,
                            },
                            "events": [
                                {"name": "gen_ai.user.message", "time_ns": 1792257801921545846,
                                 "attributes": {"content": '[{"text": "hello"}]'}},
                                {"name": "gen_ai.choice", "time_ns": 1792257802934541346,
                                 "attributes": {"message": "Hi there! How can I assist you today?",
                                                "finish_reason": "end_turn"}},
                            ],
                        },
                    ],
                },
                {
                    "scope_name": "opentelemetry.instrumentation.botocore.bedrock-agentcore",
                    "spans": [
                        {
                            # Bedrock AgentCore infra — must not be forwarded
                            "name": "Bedrock AgentCore.ListEvents",
                            "traceId": "6ad3aee9244cc512487ba36768b48bc2",
                            "spanId": "c9095b7f4e7a41b4",
                            "parentSpanId": "1116434f34966702",
                            "startTimeUnixNano": 1792257801534854621,
                            "endTimeUnixNano": 1792257801644412931,
                            "attributes": {"rpc.service": "Bedrock AgentCore", "rpc.method": "ListEvents"},
                            "events": [],
                        },
                    ],
                },
            ],
        }

    def test_aws_strands_flat_format_routed(self):
        """AWS Strands flat-format: invoke_agent * prefix span is forwarded once."""
        self.forwarder.agent_map["wxo_tracing_test"] = {
            "wxo_agent_id": "61e315a1-0749-49fc-9972-fd92068fd881",
        }
        calls = []

        def fake_post(payload, bearer_token, export_url, agent_id, tenant_id, logger=None):
            calls.append(payload)
            return "JOB-AWS"

        payload = self._make_aws_strands_payload()
        with patch("forwarder.forwarder.get_bearer_token", return_value="mock-token"), \
             patch("forwarder.forwarder.post_to_wxo", side_effect=fake_post):
            ids = self.forwarder.process_payload(
                body_bytes=json.dumps(payload).encode(),
                content_type="application/json",
            )

        self.assertEqual(ids, ["JOB-AWS"], "Expected exactly one forwarded trace from invoke_agent span")
        self.assertEqual(len(calls), 1)
        fwd_root = calls[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(fwd_root["name"], "invoke_agent wxo_tracing_test")

    def test_aws_bedrock_agentcore_spans_not_forwarded(self):
        """Bedrock AgentCore.* spans must never be forwarded standalone."""
        payload = {
            "resource_attrs": {"service.name": "wxo_tracing_test"},
            "scope_spans": [{
                "scope_name": "opentelemetry.instrumentation.botocore.bedrock-agentcore",
                "spans": [
                    {"name": "Bedrock AgentCore.CreateEvent", "traceId": "abc", "spanId": "111",
                     "startTimeUnixNano": 1000, "endTimeUnixNano": 2000, "attributes": {}, "events": []},
                    {"name": "Bedrock AgentCore.RetrieveMemoryRecords", "traceId": "abc", "spanId": "222",
                     "startTimeUnixNano": 1000, "endTimeUnixNano": 2000, "attributes": {}, "events": []},
                ],
            }],
        }
        with patch("forwarder.forwarder.get_bearer_token", return_value="mock-token"), \
             patch("forwarder.forwarder.post_to_wxo") as mock_post:
            ids = self.forwarder.process_payload(
                body_bytes=json.dumps(payload).encode(),
                content_type="application/json",
            )
        self.assertEqual(ids, [])
        mock_post.assert_not_called()

    def test_aws_execute_event_loop_cycle_not_forwarded(self):
        """execute_event_loop_cycle must never be forwarded standalone."""
        payload = {
            "resource_attrs": {"service.name": "wxo_tracing_test"},
            "scope_spans": [{
                "scope_name": "strands.telemetry.tracer",
                "spans": [
                    {"name": "execute_event_loop_cycle", "traceId": "abc", "spanId": "333",
                     "startTimeUnixNano": 1000, "endTimeUnixNano": 2000, "attributes": {}, "events": []},
                ],
            }],
        }
        with patch("forwarder.forwarder.get_bearer_token", return_value="mock-token"), \
             patch("forwarder.forwarder.post_to_wxo") as mock_post:
            ids = self.forwarder.process_payload(
                body_bytes=json.dumps(payload).encode(),
                content_type="application/json",
            )
        self.assertEqual(ids, [])
        mock_post.assert_not_called()

    def test_aws_wxo_agent_id_routed_directly(self):
        """wxo.agent.id in resource_attrs is used as a direct UUID candidate."""
        wxo_uuid = "61e315a1-0749-49fc-9972-fd92068fd881"
        payload = {
            "resource_attrs": {
                "wxo.agent.id": wxo_uuid,
                "wxo.environment": "live",
                "service.name": "my_aws_agent",
            },
            "scope_spans": [{
                "scope_name": "strands.telemetry.tracer",
                "spans": [{
                    "name": "invoke_agent MyAgent",
                    "traceId": "aabbcc", "spanId": "ddee",
                    "startTimeUnixNano": 1000, "endTimeUnixNano": 2000,
                    "attributes": {"gen_ai.usage.input_tokens": 10, "gen_ai.usage.output_tokens": 5},
                    "events": [],
                }],
            }],
        }
        seen_routing = []

        def fake_resolve(candidate_keys=None, default_name=""):
            seen_routing.append(candidate_keys)
            return {"agent_id": wxo_uuid, "agent_name": "my_aws_agent", "tenant_id": "t",
                    "export_url": "https://api.test/traces", "api_key": "test-api-key",
                    "token_url": "", "environment": "draft", "matched_key": wxo_uuid,
                    "display_name": "my_aws_agent"}

        with patch.object(self.forwarder, "resolve_wxo_agent", side_effect=fake_resolve), \
             patch("forwarder.forwarder.get_bearer_token", return_value="mock-token"), \
             patch("forwarder.forwarder.post_to_wxo", return_value="JOB-X"):
            self.forwarder.process_payload(
                body_bytes=json.dumps(payload).encode(),
                content_type="application/json",
            )

        self.assertTrue(len(seen_routing) > 0)
        keys = seen_routing[0]
        self.assertIn(wxo_uuid, keys)

    # --------------------------------------------------------------- Claude --

    def test_claude_flat_span_format_forwarded(self):
        """Claude SDK flat single-span format is parsed and forwarded."""
        self.forwarder.agent_map["Grader-agent"] = {
            "wxo_agent_id": "claude-uuid-3333",
        }
        claude_span = {
            "span_name": "anthropic.messages.create",
            "trace_id": "0x1342d6856e6096bbb60fb1bbce1539d1",
            "span_id": "0xfa0076c58037fc33",
            "status": "OK",
            "start_time_unix_nano": 1792574423142581000,
            "end_time_unix_nano": 1792574424546128000,
            "duration_ms": 1403.55,
            "resource": {
                "service.name": "Grader-agent",
                "agent.id": "agent_01GKq3KC6L1BpJfqqoCrnZ8p",
                "agent.name": "Grader-agent",
                "gen_ai.agent.id": "agent_01GKq3KC6L1BpJfqqoCrnZ8p",
                "gen_ai.agent.name": "Grader-agent",
            },
            "attributes": {
                "gen_ai.provider.name": "anthropic",
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": "claude-opus-4-5",
                "gen_ai.response.model": "claude-opus-4-5-20251101",
                "gen_ai.usage.input_tokens": 16,
                "gen_ai.usage.output_tokens": 13,
                "gen_ai.input.messages": '[{"role":"user","parts":[{"type":"text","content":"What is 2 + 2?"}]}]',
                "gen_ai.output.messages": '[{"role":"assistant","parts":[{"type":"text","content":"2 + 2 = 4"}]}]',
                "anthropic.organization.id": "1962860e-5d71-466f-b5c2-bbc3491de9b6",
                "http.response.status_code": 200,
            },
        }
        calls = []

        def fake_post(payload, bearer_token, export_url, agent_id, tenant_id, logger=None):
            calls.append(payload)
            return "JOB-CLAUDE"

        with patch("forwarder.forwarder.get_bearer_token", return_value="mock-token"), \
             patch("forwarder.forwarder.post_to_wxo", side_effect=fake_post):
            ids = self.forwarder.process_payload(
                body_bytes=json.dumps(claude_span).encode(),
                content_type="application/json",
            )

        self.assertEqual(ids, ["JOB-CLAUDE"])
        self.assertEqual(len(calls), 1)
        fwd_spans = calls[0]["resourceSpans"][0]["scopeSpans"][0]["spans"]
        root_attrs = {
            a["key"]: (a["value"].get("intValue") or a["value"].get("stringValue") or 0)
            for a in fwd_spans[0].get("attributes", [])
        }
        self.assertEqual(root_attrs.get("gen_ai.usage.input_tokens"), 16)
        self.assertEqual(root_attrs.get("gen_ai.usage.output_tokens"), 13)

    # --------------------------------------------------------------- Azure --

    def test_azure_sk_invocation_span_forwarded(self):
        """Azure Semantic Kernel agent invocation span is forwarded as a WXO trace."""
        self.forwarder.agent_map["my-sk-agent"] = {"wxo_agent_id": "azure-uuid-5555"}
        payload = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "my-sk-agent"}},
                    {"key": "gen_ai.system", "value": {"stringValue": "microsoft.semantic_kernel"}},
                ]},
                "scopeSpans": [{
                    "spans": [
                        {
                            # invocation root — must forward
                            "traceId": "aa" * 16,
                            "spanId": "bb" * 8,
                            "name": "microsoft.semantic_kernel.agent.invoke",
                            "startTimeUnixNano": 1000000,
                            "endTimeUnixNano": 2000000,
                            "attributes": [
                                {"key": "gen_ai.system",            "value": {"stringValue": "microsoft.semantic_kernel"}},
                                {"key": "gen_ai.agent.name",        "value": {"stringValue": "my-sk-agent"}},
                                {"key": "gen_ai.operation.name",    "value": {"stringValue": "invoke_agent"}},
                                {"key": "gen_ai.usage.input_tokens","value": {"intValue": 50}},
                                {"key": "gen_ai.usage.output_tokens","value": {"intValue": 25}},
                                {"key": "gen_ai.input.messages",    "value": {"stringValue": '[{"role":"user","content":"hello SK"}]'}},
                                {"key": "gen_ai.output.messages",   "value": {"stringValue": '[{"role":"assistant","content":"Hi from SK!"}]'}},
                                {"key": "az.ai.agent.thread.id",    "value": {"stringValue": "thread_sk_001"}},
                            ],
                        },
                        {
                            # subordinate LLM completion — must NOT forward
                            "traceId": "aa" * 16,
                            "spanId": "cc" * 8,
                            "parentSpanId": "bb" * 8,
                            "name": "openai.chat",
                            "startTimeUnixNano": 1100000,
                            "endTimeUnixNano": 1900000,
                            "attributes": [
                                {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                            ],
                        },
                    ],
                }],
            }]
        }
        calls = []
        with patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo", side_effect=lambda payload, **kw: calls.append(payload) or "J"):
            ids = self.forwarder.process_payload(json.dumps(payload).encode())

        self.assertEqual(len(ids), 1, "Expected exactly one forwarded trace")
        root_attrs = {a["key"]: (a["value"].get("intValue") or a["value"].get("stringValue") or 0)
                      for a in calls[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"]}
        self.assertEqual(root_attrs.get("gen_ai.usage.input_tokens"), 50)
        self.assertEqual(root_attrs.get("gen_ai.usage.output_tokens"), 25)
        # platform should be resolved from gen_ai.system
        self.assertEqual(root_attrs.get("llm.system"), "azure_ai_foundry")

    def test_azure_openai_chat_subordinate_not_forwarded(self):
        """openai.chat sub-spans must never be forwarded as standalone WXO traces."""
        payload = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "my-sk-agent"}},
                ]},
                "scopeSpans": [{
                    "spans": [
                        {"traceId": "xx", "spanId": "y1", "name": "openai.chat",
                         "startTimeUnixNano": 1000, "endTimeUnixNano": 2000,
                         "attributes": [{"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}}]},
                        {"traceId": "xx", "spanId": "y2", "name": "ChatCompletionsClient.complete",
                         "startTimeUnixNano": 1000, "endTimeUnixNano": 2000, "attributes": []},
                        {"traceId": "xx", "spanId": "y3", "name": "az.ai.inference.chat",
                         "startTimeUnixNano": 1000, "endTimeUnixNano": 2000, "attributes": []},
                    ],
                }],
            }]
        }
        with patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo") as mock_post:
            ids = self.forwarder.process_payload(json.dumps(payload).encode())
        self.assertEqual(ids, [])
        mock_post.assert_not_called()

    def test_azure_foundry_agent_run_forwarded(self):
        """Azure AI Foundry Assistants SDK agent_run span is forwarded."""
        self.forwarder.agent_map["foundry-agent"] = {"wxo_agent_id": "foundry-uuid-6666"}
        payload = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "foundry-agent"}},
                ]},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": "abcdef" * 5 + "ab",
                        "spanId": "1234567812345678",
                        "name": "agent_run",
                        "startTimeUnixNano": 1000000,
                        "endTimeUnixNano": 3000000,
                        "attributes": [
                            {"key": "gen_ai.system",              "value": {"stringValue": "az.ai.inference"}},
                            {"key": "gen_ai.agent.name",          "value": {"stringValue": "foundry-agent"}},
                            {"key": "az.ai.agent.thread.id",      "value": {"stringValue": "thread_foundry_abc"}},
                            {"key": "gen_ai.usage.input_tokens",  "value": {"intValue": 100}},
                            {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 40}},
                        ],
                    }],
                }],
            }]
        }
        captured = []
        with patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo",
                   side_effect=lambda payload, **kw: captured.append(payload) or "J"):
            ids = self.forwarder.process_payload(json.dumps(payload).encode())
        self.assertEqual(len(ids), 1)
        root_attrs = {a["key"]: (a["value"].get("intValue") or a["value"].get("stringValue") or 0)
                      for a in captured[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"]}
        self.assertEqual(root_attrs.get("gen_ai.usage.input_tokens"), 100)
        # session_id must come from az.ai.agent.thread.id
        self.assertEqual(root_attrs.get("thread.id"), "thread_foundry_abc")
        # platform resolved from gen_ai.system=az.ai.inference
        self.assertEqual(root_attrs.get("llm.system"), "azure_ai_foundry")

    # -------------------------------------------------------------- Vertex --

    def test_vertex_generate_content_prefix_forwarded(self):
        """Vertex Gemini direct SDK: 'generate_content <model>' prefix is forwarded."""
        self.forwarder.agent_map["gemini-agent"] = {"wxo_agent_id": "vertex-uuid-7777"}
        payload = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name",  "value": {"stringValue": "gemini-agent"}},
                    {"key": "gen_ai.system", "value": {"stringValue": "vertexai"}},
                ]},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": "vertex001" * 4,
                        "spanId":  "vv001122",
                        "name":    "generate_content gemini-2.0-flash",
                        "startTimeUnixNano": 1000000,
                        "endTimeUnixNano":   4000000,
                        "attributes": [
                            {"key": "gen_ai.system",              "value": {"stringValue": "vertexai"}},
                            {"key": "gen_ai.request.model",       "value": {"stringValue": "gemini-2.0-flash"}},
                            {"key": "gen_ai.usage.input_tokens",  "value": {"intValue": 200}},
                            {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 80}},
                            {"key": "gen_ai.input.messages",      "value": {"stringValue": '[{"role":"user","content":"what is 1+1?"}]'}},
                            {"key": "gen_ai.output.messages",     "value": {"stringValue": '[{"role":"assistant","content":"2"}]'}},
                        ],
                    }],
                }],
            }]
        }
        captured = []
        with patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo",
                   side_effect=lambda payload, **kw: captured.append(payload) or "J"):
            ids = self.forwarder.process_payload(json.dumps(payload).encode())

        self.assertEqual(len(ids), 1)
        root_attrs = {a["key"]: (a["value"].get("intValue") or a["value"].get("stringValue") or 0)
                      for a in captured[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["attributes"]}
        self.assertEqual(root_attrs.get("gen_ai.usage.input_tokens"), 200)
        self.assertEqual(root_attrs.get("gen_ai.usage.output_tokens"), 80)
        self.assertEqual(root_attrs.get("llm.system"), "vertex_ai")

    def test_vertex_grpc_infra_spans_not_forwarded(self):
        """google.cloud.* and PredictionServiceClient.* spans must not be forwarded."""
        payload = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "gemini-agent"}},
                ]},
                "scopeSpans": [{
                    "spans": [
                        {"traceId": "x", "spanId": "a1", "name": "PredictionServiceClient.generate_content",
                         "startTimeUnixNano": 1000, "endTimeUnixNano": 2000, "attributes": []},
                        {"traceId": "x", "spanId": "a2", "name": "google.cloud.aiplatform.prediction",
                         "startTimeUnixNano": 1000, "endTimeUnixNano": 2000, "attributes": []},
                        {"traceId": "x", "spanId": "a3", "name": "google.cloud.something.else",
                         "startTimeUnixNano": 1000, "endTimeUnixNano": 2000, "attributes": []},
                    ],
                }],
            }]
        }
        with patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo") as mock_post:
            ids = self.forwarder.process_payload(json.dumps(payload).encode())
        self.assertEqual(ids, [])
        mock_post.assert_not_called()

    def test_platform_resolution_from_gen_ai_system(self):
        """_resolve_platform correctly maps gen_ai.system values to platform tags."""
        from forwarder.forwarder import _resolve_platform
        cases = [
            ({"gen_ai.system": "az.ai.inference"},           {}, "azure_ai_foundry"),
            ({"gen_ai.system": "microsoft.semantic_kernel"},  {}, "azure_ai_foundry"),
            ({"gen_ai.system": "aws.bedrock"},                {}, "aws_agentcore"),
            ({"gen_ai.system": "strands-agents"},             {}, "aws_agentcore"),
            ({"gen_ai.system": "anthropic"},                  {}, "claude-platform"),
            ({"gen_ai.system": "vertexai"},                   {}, "vertex_ai"),
            ({"gen_ai.system": "openai"},                     {}, "openai"),
            ({},  {"service.name": "my-custom-agent"},            "my-custom-agent"),
            ({},  {},                                              "external_agent"),
        ]
        for attrs, res_attrs, expected in cases:
            with self.subTest(attrs=attrs):
                self.assertEqual(_resolve_platform(attrs, res_attrs), expected)

    def test_claude_flat_span_prompt_and_response_extracted(self):
        """gen_ai.input/output.messages in Claude flat span are unwrapped to plain text."""
        self.forwarder.agent_map["Grader-agent"] = {"wxo_agent_id": "claude-uuid-3333"}
        claude_span = {
            "span_name": "anthropic.messages.create",
            "trace_id": "deadbeef",
            "span_id": "cafebabe",
            "start_time_unix_nano": 1000000,
            "end_time_unix_nano": 2000000,
            "resource": {"service.name": "Grader-agent"},
            "attributes": {
                "gen_ai.request.model": "claude-opus-4-5",
                "gen_ai.usage.input_tokens": 5,
                "gen_ai.usage.output_tokens": 3,
                "gen_ai.input.messages": '[{"role":"user","parts":[{"type":"text","content":"hello claude"}]}]',
                "gen_ai.output.messages": '[{"role":"assistant","parts":[{"type":"text","content":"Hello!"}]}]',
            },
        }
        captured = []
        with patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo",
                   side_effect=lambda payload, **kw: captured.append(payload) or "J"):
            self.forwarder.process_payload(json.dumps(claude_span).encode())

        self.assertEqual(len(captured), 1)
        root = captured[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        attr_map = {a["key"]: a["value"].get("stringValue", "") for a in root["attributes"]}
        self.assertEqual(attr_map.get("gen_ai.task.input"), "hello claude")
        self.assertEqual(attr_map.get("gen_ai.task.output"), "Hello!")


    # ---------------------------------------------------------- Scores / Eval --

    def test_extract_scores_numeric(self):
        """eval.* and score.* attributes with numeric-like string values become
        NUMERIC scores."""
        attrs = {
            "eval.relevance":     "0.92",
            "eval.toxicity":      "0.00",
            "score.faithfulness": "0.87",
            "llm.eval.groundedness": 0.75,
        }
        scores = OtlpForwarder._extract_scores(attrs)
        self.assertEqual(len(scores), 4)
        by_name = {s["name"]: s for s in scores}
        self.assertEqual(by_name["relevance"]["dataType"], "NUMERIC")
        self.assertAlmostEqual(by_name["relevance"]["value"], 0.92)
        self.assertEqual(by_name["toxicity"]["dataType"], "NUMERIC")
        self.assertAlmostEqual(by_name["toxicity"]["value"], 0.0)
        self.assertAlmostEqual(by_name["faithfulness"]["value"], 0.87)
        self.assertAlmostEqual(by_name["groundedness"]["value"], 0.75)

    def test_extract_scores_categorical(self):
        """eval.* attributes with non-numeric string values become CATEGORICAL
        scores, preserving the string in stringValue."""
        attrs = {
            "eval.sentiment": "positive",
            "langfuse.score.quality": "high",
        }
        scores = OtlpForwarder._extract_scores(attrs)
        by_name = {s["name"]: s for s in scores}
        self.assertEqual(by_name["sentiment"]["dataType"], "CATEGORICAL")
        self.assertEqual(by_name["sentiment"]["stringValue"], "positive")
        self.assertEqual(by_name["sentiment"]["value"], 0.0)
        self.assertEqual(by_name["quality"]["dataType"], "CATEGORICAL")

    def test_extract_scores_ignores_non_score_attrs(self):
        """Attributes not matching a score prefix must be ignored."""
        attrs = {
            "gen_ai.request.model": "claude-opus-5-5",
            "gen_ai.usage.input_tokens": 100,
            "session.id": "abc",
        }
        scores = OtlpForwarder._extract_scores(attrs)
        self.assertEqual(scores, [])

    def test_extract_scores_dedup(self):
        """The same score name under two different prefixes only appears once."""
        attrs = {
            "eval.relevance":         "0.9",
            "eval.score.relevance":   "0.8",  # second hit — must be skipped
        }
        scores = OtlpForwarder._extract_scores(attrs)
        names = [s["name"] for s in scores]
        self.assertEqual(names.count("relevance"), 1)

    def test_process_payload_posts_scores_after_trace(self):
        """When a span carries eval.* attributes, post_scores_to_wxo must be
        called once after post_to_wxo succeeds, with the correct trace_id and
        score names."""
        score_calls = []

        def fake_post_scores(scores, trace_id, bearer_token, export_url,
                             agent_id, tenant_id, logger=None):
            score_calls.append({"scores": scores, "trace_id": trace_id})
            return True

        sample_otlp = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "default"}},
                ]},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": "abc123",
                        "spanId": "span001",
                        "name": "invoke_agent",
                        "startTimeUnixNano": 1_000_000_000,
                        "endTimeUnixNano":   2_000_000_000,
                        "attributes": [
                            {"key": "gen_ai.prompt",      "value": {"stringValue": "hi"}},
                            {"key": "gen_ai.completion",  "value": {"stringValue": "hello"}},
                            {"key": "eval.relevance",     "value": {"stringValue": "0.95"}},
                            {"key": "eval.toxicity",      "value": {"stringValue": "0.01"}},
                        ],
                        "events": [],
                    }]
                }]
            }]
        }

        with patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo", return_value="TRACE-ABC"), \
             patch("forwarder.forwarder.post_scores_to_wxo", side_effect=fake_post_scores):
            ids = self.forwarder.process_payload(
                body_bytes=json.dumps(sample_otlp).encode(),
                content_type="application/json",
            )

        self.assertEqual(ids, ["TRACE-ABC"])
        self.assertEqual(len(score_calls), 1)
        self.assertEqual(score_calls[0]["trace_id"], "TRACE-ABC")
        score_names = {s["name"] for s in score_calls[0]["scores"]}
        self.assertIn("relevance", score_names)
        self.assertIn("toxicity", score_names)

    def test_process_payload_no_scores_when_no_eval_attrs(self):
        """When a span has no eval.* attributes, post_scores_to_wxo must not be
        called at all."""
        sample_otlp = {
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "default"}},
                ]},
                "scopeSpans": [{
                    "spans": [{
                        "traceId": "xyz",
                        "spanId": "s1",
                        "name": "invoke_agent",
                        "startTimeUnixNano": 1_000_000_000,
                        "endTimeUnixNano":   2_000_000_000,
                        "attributes": [
                            {"key": "gen_ai.prompt",     "value": {"stringValue": "q"}},
                            {"key": "gen_ai.completion", "value": {"stringValue": "a"}},
                        ],
                        "events": [],
                    }]
                }]
            }]
        }
        with patch("forwarder.forwarder.get_bearer_token", return_value="tok"), \
             patch("forwarder.forwarder.post_to_wxo", return_value="JX"), \
             patch("forwarder.forwarder.post_scores_to_wxo") as mock_scores:
            self.forwarder.process_payload(
                body_bytes=json.dumps(sample_otlp).encode(),
                content_type="application/json",
            )
        mock_scores.assert_not_called()

    def test_post_scores_to_wxo_derives_scores_url(self):
        """post_scores_to_wxo replaces inject/traces with inject/scores in the URL."""
        captured_urls = []

        class FakeResp:
            status = 200
            def read(self): return b"{}"
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen(req, timeout=None, context=None):
            captured_urls.append(req.full_url)
            return FakeResp()

        scores = [{"name": "relevance", "value": 0.9, "dataType": "NUMERIC"}]
        with patch("forwarder.forwarder.urlopen", side_effect=fake_urlopen):
            result = post_scores_to_wxo(
                scores=scores,
                trace_id="trace-001",
                bearer_token="tok",
                export_url="https://api.test/inject/traces",
                agent_id="agent-a",
                tenant_id="tenant-t",
            )

        self.assertTrue(result)
        self.assertEqual(len(captured_urls), 1)
        self.assertIn("inject/scores", captured_urls[0])
        self.assertNotIn("inject/traces", captured_urls[0])


if __name__ == "__main__":
    unittest.main()

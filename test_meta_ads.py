"""Safety and behavior tests. Meta calls are mocked; no ads or messages are sent."""
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import app


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "Z1_ADMIN_USER": "test-admin", "Z1_ADMIN_PASSWORD": "test-password",
            "Z1_ADS_DB_PATH": self.tmp.name + "/ads.sqlite3",
            "META_AD_ACCOUNT_ID": "act_123456", "META_ADS_ACCESS_TOKEN": "test-secret-never-returned",
        })
        self.env.start()
        self.client = TestClient(app, base_url="https://testserver")
        self.client.auth = ("test-admin", "test-password")
        self.headers = {"Origin": "https://testserver"}

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.tmp.cleanup()

    def draft(self, **overrides):
        payload = {"name": "Campanha Zyone", "objective": "OUTCOME_LEADS", "notes": "Plano interno"}
        payload.update(overrides)
        r = self.client.post("/api/ads/drafts", json=payload, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def create(self, draft):
        return self.client.post(f'/api/ads/drafts/{draft["id"]}/create',
                                json={"confirm_paused_creation": True}, headers=self.headers)

    def test_drafts_work_without_credentials_and_never_call_meta(self):
        with patch.dict(os.environ, {"META_ADS_ACCESS_TOKEN": "", "META_AD_ACCOUNT_ID": ""}), patch("meta_ads.graph_request") as graph:
            d = self.draft()
            self.assertEqual(d["campaign"]["status"], "PAUSED")
            self.assertEqual(self.create(d).status_code, 409)
            graph.assert_not_called()
            self.assertFalse(self.client.get('/api/ads/status').json()['configured'])

    def test_only_paused_payload_sent_and_repeated_confirm_is_idempotent(self):
        d = self.draft()
        with patch("meta_ads.graph_request", return_value={"id": "987654"}) as graph:
            self.assertEqual(self.create(d).json()["campaign_id"], "987654")
            self.assertEqual(self.create(d).json()["campaign_id"], "987654")
            self.assertEqual(graph.call_count, 1)
            method, path, body = graph.call_args.args
            self.assertEqual((method, path, body["status"]), ("POST", "act_123456/campaigns", "PAUSED"))
            self.assertNotIn("notes", body)
            self.assertNotIn("daily_budget", body)

    def test_duplicate_concurrent_requests_do_not_duplicate_campaigns(self):
        d = self.draft()
        with patch("meta_ads.graph_request", return_value={"id": "987654"}) as graph:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: self.create(d), range(2)))
            self.assertIn(200, [r.status_code for r in responses])
            self.assertEqual(graph.call_count, 1)

    def test_uncertain_response_is_recorded_and_never_retried(self):
        d = self.draft()
        with patch("meta_ads.graph_request", side_effect=HTTPException(502, "Resultado incerto")) as graph:
            self.assertEqual(self.create(d).status_code, 502)
            self.assertEqual(self.create(d).status_code, 409)
            self.assertEqual(graph.call_count, 1)
        self.assertEqual(self.client.get('/api/ads/drafts').json()['drafts'][0]['state'], 'unknown')

    def test_account_change_requires_new_review(self):
        d = self.draft()
        with patch.dict(os.environ, {"META_AD_ACCOUNT_ID": "456789"}), patch("meta_ads.graph_request") as graph:
            self.assertEqual(self.create(d).status_code, 409)
            graph.assert_not_called()

    def test_active_status_extra_fields_and_unconfirmed_creation_are_rejected(self):
        r = self.client.post('/api/ads/drafts', headers=self.headers,
                             json={"name": "X", "objective": "OUTCOME_LEADS", "status": "ACTIVE"})
        self.assertEqual(r.status_code, 422)
        d = self.draft()
        with patch("meta_ads.graph_request") as graph:
            for confirm in (False, "true", 1):
                r = self.client.post(f'/api/ads/drafts/{d["id"]}/create', headers=self.headers,
                                     json={"confirm_paused_creation": confirm})
                self.assertEqual(r.status_code, 422)
            graph.assert_not_called()

    def test_authentication_and_csrf_guard(self):
        self.assertEqual(TestClient(app).get('/api/ads/drafts', follow_redirects=False).status_code, 303)
        for origin in (None, 'https://foreign.example'):
            h = {"Origin": origin} if origin else {}
            self.assertEqual(self.client.post('/api/ads/drafts', headers=h,
                json={"name": "Test", "objective": "OUTCOME_LEADS"}).status_code, 403)

    def test_connection_check_and_secrets_not_returned(self):
        with patch('meta_ads.graph_request', return_value={"id": "act_123456", "name": "Conta Z1", "currency": "BRL", "account_status": 1}) as graph:
            r = self.client.get('/api/ads/account')
            self.assertEqual(r.json()['currency'], 'BRL')
            self.assertEqual(graph.call_args.args[0], 'GET')
        d = self.draft()
        for route in ('/api/ads/status', '/api/ads/drafts', '/meta-ads'):
            r = self.client.get(route)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn('test-secret-never-returned', r.text)

    def test_objective_category_and_blank_name_validation(self):
        for changes in ({"objective": "INVALID"}, {"name": "  "}, {"special_ad_categories": ["INVALID"]}):
            payload = {"name": "Test", "objective": "OUTCOME_LEADS", **changes}
            self.assertEqual(self.client.post('/api/ads/drafts', headers=self.headers, json=payload).status_code, 422)


if __name__ == '__main__':
    unittest.main()

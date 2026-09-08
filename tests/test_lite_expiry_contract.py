import unittest
from unittest.mock import patch
from lite_pos.api import LiteApiClient


class LiteExpiryContractTests(unittest.TestCase):
    def test_expiry_and_batch_are_sent_to_shared_stock_endpoint(self):
        client = LiteApiClient('http://localhost')
        with patch.object(client, '_request', return_value={'product': {'id': 1}}) as request:
            for expiry in ['2027-09-08', '']:
                client.adjust_stock(1, 2, batch_no=' LOT-1 ', expire_date=expiry)
                self.assertEqual(request.call_args.args, ('POST', '/api/stock/adjust'))
                payload = request.call_args.kwargs['json']
                self.assertEqual(payload['batch_no'], 'LOT-1')
                self.assertEqual(payload['expire_date'], expiry)

    def test_legacy_call_without_expiry_still_means_no_expiry(self):
        client = LiteApiClient('http://localhost')
        with patch.object(client, '_request', return_value={}) as request:
            client.adjust_stock(1, 2)
            self.assertEqual(request.call_args.kwargs['json']['expire_date'], '')


if __name__ == '__main__':
    unittest.main()

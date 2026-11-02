import unittest
import engine

class ReviewBehavior(unittest.TestCase):
    def test_split_shipments_and_completed_return(self):
        r=engine.review('C03','clean')
        self.assertEqual(r['fields']['shipment_ids'],['SYN-OUT-C03-01','SYN-OUT-C03-02'])
        self.assertEqual((r['result']['remaining'],r['result']['excess'],r['result']['state']),(6,2,'불일치'))
    def test_conflicting_label_is_not_overwritten_from_order(self):
        r=engine.review('C02','clean')
        self.assertNotEqual(r['fields']['part'],r['fields']['label_part'])
        self.assertEqual(r['result']['state'],'근거 충돌')
    def test_obscured_label_requires_abstention(self):
        r=engine.review('C06','clean')
        self.assertIsNone(r['fields']['label_part'])
        self.assertEqual(r['result']['state'],'자료 부족')
    def test_missing_damage_photos_not_inferred_from_claim(self):
        r=engine.review('C04','clean')
        self.assertEqual(r['result']['state'],'자료 부족')
        self.assertEqual(next(c for c in r['result']['checks'] if c['name']=='파손 증빙')['state'],'자료 부족')
    def test_supplier_opinion_is_not_customer_request(self):
        r=engine.review('C05','clean')
        self.assertEqual((r['fields']['quantity'],r['fields']['vendor_quantity']),(4,2))
        self.assertEqual(r['result']['state'],'근거 충돌')
    def test_policy_uses_shipment_date_and_inclusive_limit(self):
        r=engine.review('C01','clean');fields=dict(r['fields'])
        self.assertEqual(r['result']['policies'][0]['id'],'SYN-R1')
        fields['request_date']='2026-10-30'
        at_limit=engine.evaluate('C01',fields,r['documents'])
        self.assertEqual(at_limit['state'],'통과')
        fields['request_date']='2026-10-31'
        beyond=engine.evaluate('C01',fields,r['documents'])
        self.assertEqual(beyond['state'],'불일치')
    def test_unknown_transaction_cannot_pass(self):
        r=engine.review('C01','clean');fields=dict(r['fields']);fields['shipment_ids']=['SYN-OUT-C01-99']
        self.assertEqual(engine.evaluate('C01',fields,r['documents'])['state'],'자료 부족')

if __name__=='__main__':unittest.main()

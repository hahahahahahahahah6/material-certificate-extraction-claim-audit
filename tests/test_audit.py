import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from material_certificate_extraction_claim_audit import phrases
from material_certificate_extraction_claim_audit.audit import audit, source_evidence, claims
from material_certificate_extraction_claim_audit.__main__ import main

EXPECTED_POS = ('material certificate extraction', 'extract material certificates', 'extracts material certificates', 'extracting material certificates', 'extract material certificate', 'extracts material certificate', 'extracting material certificate', 'material certificate parsing', 'material certificate parser', 'parse material certificates', 'parses material certificates', 'parse material certificate', 'parses material certificate', 'material certificate scanning', 'material certificate scanner', 'scan material certificates', 'scans material certificates', 'scan material certificate', 'scans material certificate', 'mill test certificate extraction', 'extract mill test certificates', 'extracts mill test certificates', 'extracting mill test certificates', 'mill test certificate parsing', 'mill test certificate parser', 'parse mill test certificates', 'parses mill test certificates', 'mill test certificate scanning', 'mill test certificate scanner', 'scan mill test certificates', 'scans mill test certificates', 'material test certificate extraction', 'extract material test certificates', 'extracts material test certificates', 'extracting material test certificates', 'extract material test certificate', 'extracts material test certificate', 'extracting material test certificate', 'material test certificate parsing', 'material test certificate parser', 'parse material test certificates', 'parses material test certificates', 'parse material test certificate', 'parses material test certificate', 'material test certificate scanning', 'material test certificate scanner', 'scan material test certificates', 'scans material test certificates', 'scan material test certificate', 'scans material test certificate')
EXPECTED_NEG = ('no material certificate extraction', 'does not extract material certificates', 'does not extract material certificate', 'does not support material certificate extraction', 'without material certificate extraction', 'no material certificate parser', 'does not parse material certificates', 'does not parse material certificate', 'no mill test certificate extraction', 'does not extract mill test certificates', 'does not support mill test certificate extraction', 'without mill test certificate extraction', 'no mill test certificate parser', 'does not parse mill test certificates', 'no material test certificate extraction', 'does not extract material test certificates', 'does not extract material test certificate', 'does not support material test certificate extraction', 'without material test certificate extraction', 'no material test certificate parser', 'does not parse material test certificates', 'does not parse material test certificate', 'no material certificate scanner', 'material certificate extraction not supported')
EXPECTED_NAMES = ('extract_material_certificate', 'parse_material_certificate', 'extract_material_certificates', 'parse_material_certificates', 'extract_mill_test_certificate', 'parse_mill_test_certificate', 'extract_material_test_certificate', 'parse_material_test_certificate', 'extract_material_test_certificates', 'parse_material_test_certificates', 'material_certificate_extraction', 'material_certificate_extractor', 'material_certificate_parser', 'mill_test_certificate_extraction', 'mill_test_certificate_extractor', 'mill_test_certificate_parser', 'material_test_certificate_extraction', 'material_test_certificate_extractor', 'material_test_certificate_parser', 'extract_material_certificate_data', 'parse_material_certificate_data', 'material_certificate_scan', 'material_certificate_scanner', 'scan_material_certificate')

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")
        return file

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_phrase_oracle(self):
        tree = ast.parse(Path(phrases.__file__).read_text())
        values = {node.targets[0].id: ast.literal_eval(node.value)
                  for node in tree.body if isinstance(node, ast.Assign)}
        self.assertEqual(values['MATERIALCERTIFICATEEXTRACTION'], EXPECTED_POS)
        self.assertEqual(values['NOMATERIALCERTIFICATEEXTRACTION'], EXPECTED_NEG)
        self.assertEqual(values['GENERIC_NAMES'], EXPECTED_NAMES)
        self.assertEqual(tuple(map(len, (EXPECTED_POS, EXPECTED_NEG, EXPECTED_NAMES))), (50,24,24))
        self.assertEqual(len(set(EXPECTED_NAMES)), 24)

    def test_bad(self):
        self.put('README.md', 'extract material certificates')
        code, out, _ = self.run_cli('audit', str(self.root), '--json')
        report = json.loads(out)
        self.assertEqual(code, 2)
        self.assertEqual(report['verdict'], 'FAIL')
        self.assertEqual(report['findings'][0]['rule'], 'documented-material-certificate-extraction-claim-false')
        self.assertEqual(report['findings'][0]['severity'], 'HIGH')
        self.assertTrue(report['findings'][0]['message'])
        self.assertIn('production_evidence', report)
        self.assertIn('test_evidence', report)

    def test_good(self):
        self.put('README.md', 'extract material certificates')
        self.put('app.py', 'x.extract_material_certificate()')
        self.assertEqual(self.run_cli('audit', str(self.root))[0], 0)

    def test_denial(self):
        self.put('README.md', 'does not extract material certificates')
        self.put('app.py', 'x.extract_material_certificate()')
        result = audit(self.root)
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['rule'], 'documented-no-material-certificate-extraction-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertEqual(self.run_cli('audit', str(self.root))[0], 2)

    def test_test_only(self):
        self.put('README.md', 'material certificate extraction')
        self.put('tests/proof.py', 'x.extract_material_certificate()')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')
        self.assertEqual(self.run_cli('audit', str(self.root))[0], 0)
        self.assertEqual(self.run_cli('audit', str(self.root), '--fail-on', 'medium')[0], 2)

    def test_no_claim(self):
        self.put('README.md', 'Ordinary project')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_no_source_denial(self):
        self.put('README.md', 'no material certificate extraction')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_split_modules(self):
        self.put('README.md', 'material certificate extraction')
        self.put('a.py', 'import mindee; c = mindee.Client()')
        self.put('b.py', 'import mindee; c.parse(product.MaterialCertificateV1, src)')
        self.assertFalse(audit(self.root)['production_evidence'])

    def test_docs_selection(self):
        self.put('other.md', 'material certificate extraction')
        self.assertFalse(audit(self.root)['findings'])
        self.put('nested/docs/guide.md', 'material certificate extraction')
        self.assertEqual(len(audit(self.root)['findings']), 1)

    def test_symlinks(self):
        outside = self.put('fixtures/real.py', 'x.extract_material_certificate()')
        (self.root/'linked.py').symlink_to(outside)
        (self.root/'linked').symlink_to(outside.parent, target_is_directory=True)
        self.assertFalse(audit(self.root)['production_evidence'])
        self.put('fixtures/README.md', 'material certificate extraction')
        (self.root/'README.md').symlink_to(self.root/'fixtures/README.md')
        self.assertFalse(audit(self.root)['findings'])

    def test_ignore(self):
        self.put('README.md', 'material certificate extraction')
        self.put('vendor/app.py', 'x.extract_material_certificate()')
        self.assertTrue(audit(self.root)['production_evidence'])
        self.assertFalse(audit(self.root, ignores=['vendor'])['production_evidence'])
        self.assertEqual(self.run_cli('audit', str(self.root), '--ignore', 'vendor', '--ignore', 'build')[0], 2)

    def test_cli_errors(self):
        for args in [[], ['wat'], ['audit','/does/not/exist'], ['audit','--fail-on','HIGH'], ['audit','--unknown']]:
            self.assertEqual(self.run_cli(*args)[0], 1)

    def test_version(self):
        self.assertEqual(self.run_cli('--version')[:2], (0, '0.1.0\n'))

    def test_module_entrypoint(self):
        p = subprocess.run([sys.executable, '-m', 'material_certificate_extraction_claim_audit', '--version'], capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, '0.1.0\n'))

    def test_readme_self_audit(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(audit(root)['verdict'], 'PASS')
        self.assertFalse(claims((root/'README.md').read_text()))

    def test_default_repo_verbose(self):
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            self.put('app.py', 'x.extract_material_certificate()')
            code, out, _ = self.run_cli('audit', '--verbose')
            self.assertEqual(code, 0)
            self.assertIn('app.py:1', out)
        finally:
            os.chdir(previous)


def positive_case(code):
    def test(self):
        self.assertTrue(source_evidence(code), code)
    return test


def negative_case(code):
    def test(self):
        self.assertEqual(source_evidence(code), [], code)
    return test


def phrase_case(phrase, denial=False):
    def test(self):
        found = claims(phrase)
        self.assertEqual({x['family'] for x in found}, {'negative' if denial else 'positive'})
    return test

for i, phrase in enumerate(EXPECTED_POS):
    setattr(AuditTests, 'test_positive_phrase_%02d' % i, phrase_case(phrase))
for i, phrase in enumerate(EXPECTED_NEG):
    setattr(AuditTests, 'test_negative_phrase_%02d' % i, phrase_case(phrase, True))
for i, name in enumerate(EXPECTED_NAMES):
    for kind, code in [('attribute', 'x.%s()' % name), ('import', 'from vendor import %s as route\nroute()' % name)]:
        setattr(AuditTests, 'test_generic_%s_%02d' % (kind, i), positive_case(code))
    setattr(AuditTests, 'test_bare_%02d' % i, negative_case(name+'()'))

PRODUCTS = 'InvoiceV4 ReceiptV5 PassportV1 FinancialDocumentV1 BankCheckV1 BankAccountDetailsV1 BankAccountDetailsV2 PayslipV2 PayslipV3 NutritionFactsLabelV1 HealthcareCardV1 BusinessCardV1 CustomV1 GeneratedV1 BillOfLadingV1 ResumeV1 DeliveryNoteV1 DriverLicenseV1 IdCardV1 InternationalIdV2 CarteGriseV1 EnergyBillV1 BarcodeReaderV1 CropperV1 TypeMaterialCertificateV1'.split()
for product in PRODUCTS:
    setattr(AuditTests, 'test_other_product_'+product, negative_case('import mindee\nc = mindee.Client()\nc.parse(product.%s, src)' % product))

POSITIVE_SOURCES = [
    'from mindee import product\nc=mindee.Client()\nc.parse(product.MaterialCertificateV1)',
    'import mindee\nc=mindee.Client()\nc.parse(product.MaterialCertificateV1, src)',
    'from mindee import Client\nfrom mindee.product import MaterialCertificateV1\nc=Client()\nc.parse(MaterialCertificateV1, src)',
    'import mindee\nc=mindee.Client()\nc.parse(mindee.product.MaterialCertificateV1, src)',
    'import mindee\nc=mindee.Client()\nc.parse(mindee.product.material_certificate.MaterialCertificateV1, src)',
    'from mindee import Client as C\nc=C()\nc.parse(product_class=product.MaterialCertificateV1)',
    'import mindee as md\nc=md.Client()\nc.parse(product.MaterialCertificateV1)',
    'from vendor import extract_material_certificate as f\ng=f\ng()',
    'from vendor import extract_material_certificate as f\ng: object=f\ng()',
]
for i, code in enumerate(POSITIVE_SOURCES):
    setattr(AuditTests, 'test_sdk_alias_%02d' % i, positive_case(code))

NEGATIVE_SOURCES = [
    'import mindee', 'import veryfi', 'import azure.ai.documentintelligence', 'import google.cloud.documentai',
    'import mindee\nc=mindee.Client()', 'c.parse(product.MaterialCertificateV1)',
    'from mindee import Client\ndef Client(): pass\nClient()\nc.parse(product.MaterialCertificateV1)',
    'import mindee\nmindee=object()\nmindee.Client()\nc.parse(product.MaterialCertificateV1)',
    'from vendor import extract_material_certificate\ndef extract_material_certificate(): pass\nextract_material_certificate()',
    'class C:\n def extract_material_certificate(self): pass\nx.extract_material_certificate()',
    'from vendor import extract_material_certificate as f\nf: object = None\nf()',
    'from vendor import extract_material_certificate as f\nwith ctx() as f: f()',
    'from vendor import extract_material_certificate as f\nasync def a():\n async with ctx() as f: f()',
    'from vendor import extract_material_certificate\nextract_material_certificate',
    '"x.extract_material_certificate()" # x.extract_material_certificate()',
    'x.extract_material_certificate(',
    'subprocess.run(["mindee", "parse", "material_certificate"])',
    'subprocess.run(["veryfi", "material_certificate"])',
    'requests.post("https://api.veryfi.com/api/v8/partner/documents")',
    'x.universal_ai(model="ocr/invoice_parser/affinda")',
    'x.universal_ai(model="ocr/resume_parser/affinda")',
    'LlamaParse().load_data("cert.pdf")', 'nanonets.predict(model_id="opaque")',
    'docsumo.upload("cert.pdf")', 'mindee.ClientV2().enqueue_and_get_inference(model_id="opaque")',
    'import re\ntext=x.image_to_string(img)\nfields={"heat_number": re.search("heat",text)}',
    'text="mill test certificate"\ntext.split()',
]
for name in 'extract_certificate parse_certificate certificate_extraction extract_certificate_of_conformity extract_material_safety_data_sheet extract_mill_test_report extract_material_test_report extract_text image_to_string read_csv read_excel read_pdf convert_into extract_table extract_tables find_table find_tables process_document batch_process_documents analyze_document analyze_expense analyze_id start_document_analysis get_expense_analysis process_any_document process_any_document_url process_document_url process_w2_document process_w9_document process_w8_document process_check process_check_url process_check_with_remittance process_check_with_remittance_url process_bank_statement_document process_bank_statement_document_url process_bussines_card_document process_bussines_card_document_url classify_document get_business_cards get_business_card delete_business_card process_material_certificate_document process_material_certificate_document_url'.split():
    NEGATIVE_SOURCES.append('x.%s()' % name)
for model in 'invoice receipt layout read idDocument check.us tax.us bankStatement.us payStub.us healthInsuranceCard.us businessCard creditCard contract mortgage.us.1003 vaccinationCard materialCertificate'.split():
    NEGATIVE_SOURCES.append('x.begin_analyze_document("prebuilt-%s", doc)' % model)
for vendor in ['abbyy', 'rossum', 'klippa', 'parseur', 'extend']:
    NEGATIVE_SOURCES.append('%s.extract(model_id="opaque")' % vendor)
for i, code in enumerate(NEGATIVE_SOURCES):
    setattr(AuditTests, 'test_non_evidence_%03d' % i, negative_case(code))

for i, path in enumerate(['tests/a.py', 'test_app.py', 'app_test.py', 'fixtures/app.py', 'docs/app.py', 'examples/app.py']):
    def test(self, path=path):
        self.put(path, 'x.extract_material_certificate()')
        result = audit(self.root)
        self.assertFalse(result['production_evidence'])
        self.assertEqual(bool(result['test_evidence']), path.startswith('tests/') or path.startswith('test_') or path.endswith('_test.py'))
    setattr(AuditTests, 'test_excluded_path_%d' % i, test)

for i, text in enumerate(['```\nmaterial certificate extraction\n```', '   ~~~text\nmaterial certificate extraction\n   ~~~', '````\n```\nmaterial certificate extraction\n````']):
    def test(self, text=text): self.assertFalse(claims(text))
    setattr(AuditTests, 'test_fences_%d' % i, test)

for i, text in enumerate(['`extract material certificates`', 'EXTRACT-MATERIAL-CERTIFICATES', 'extract  material\ncertificates']):
    def test(self, text=text): self.assertEqual(claims(text)[0]['family'], 'positive')
    setattr(AuditTests, 'test_normalization_%d' % i, test)

class MatchingTests(unittest.TestCase):
    def test_contraction(self):
        self.assertEqual({x['family'] for x in claims("doesn't extract material certificates")}, {'negative'})
    def test_boundaries(self):
        self.assertFalse(claims('prematerial certificate extractionist'))
    def test_paragraphs(self):
        self.assertFalse(claims('extract material\n\ncertificates'))
    def test_denial_plus_positive(self):
        self.assertEqual({x['family'] for x in claims('no material certificate extraction; extract material certificates')}, {'positive','negative'})

if __name__ == '__main__':
    unittest.main()

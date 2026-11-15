# Documentation claim auditor

An offline static audit tool that compares documentation promises with Python source fingerprints. It reads root README.md and Markdown files with a docs path component, parses source with AST, and never executes inspected code. Runtime uses only the standard library, makes no network calls, sends no telemetry, and writes no files. Requires Python 3.9 or newer; MIT licensed.

## Usage

```sh
python3 -m pip install .
material-certificate-extraction-claim-audit --version
material-certificate-extraction-claim-audit audit /path/to/repo --json
python3 -m material_certificate_extraction_claim_audit audit . --verbose
material-certificate-extraction-claim-audit audit . --fail-on medium --ignore vendor --ignore build
python3 -m unittest discover
python3 -m build
```

Version 0.1.0. The repository defaults to the current directory. Each ignore option accepts one relative path prefix; repeat the option for multiple prefixes. Failure thresholds are lowercase high (default) and medium. Exit codes: 0 for PASS, 2 for findings at or above the threshold, 1 for usage or I/O errors. JSON contains verdict, findings (rule, severity, message, locations), production_evidence, and test_evidence. Verbose output includes evidence paths and line numbers. Findings below the selected threshold remain visible.

```text
Claims without production evidence:
  documented-material-certificate-extraction-claim-false HIGH
  MEDIUM when evidence exists only in tests
Denials contradicted by production evidence:
  documented-no-material-certificate-extraction-claim-false HIGH
```

At most one finding is emitted per family. A claim without source files fails; a denial without source passes. Evidence is not required when documentation makes no listed claim.

## Matching and evidence

Fenced code blocks using backticks or tildes, indented by up to three spaces, are excluded. Inline code counts. Paragraphs split on blank lines. Matching lowercases text, expands contractions, replaces hyphens with spaces, and collapses whitespace. Exact phrases use word boundaries, longest first with alphabetical ties. Denial spans are removed before positive matching. The complete fixed vocabularies are below.

Symlinked files and directories are excluded. Source under fixtures, docs, or examples supplies no evidence. Files under tests or named test_*.py or *_test.py supply only test evidence. Invalid syntax supplies none. Imports, aliases, assignments, annotated assignments, and with/async-with optional bindings are tracked per module. Local function, method, or class definitions shadow route names. Each route must occur within a single module; evidence from separate modules is never combined.

```text
Accepted SDK route: import mindee, construct mindee.Client (including
import aliases), and call .parse with MaterialCertificateV1 in one module.
The product argument must be a Name exactly MaterialCertificateV1 or an
Attribute with that exact final name; positional and keyword arguments count.
Exports: mindee.product.MaterialCertificateV1 and
mindee.product.material_certificate.MaterialCertificateV1.
There is no TypeMaterialCertificateV1 form: SDK 4.22.0 has no mindee/documents module.

MaterialCertificateV1 is a 4.x-only fingerprint. In the verified 4.22.0
wheel (2026-11-14), mindee/product/material_certificate/material_certificate_v1.py
defines class MaterialCertificateV1(Inference), endpoint_name
"material_certificate", endpoint_version "1". The document is
"Material Certificate API version 1.0" with certificate_type, heat_number, norm.
The verified 5.4.0 wheel has zero material_certificate files and zero
MaterialCertificate hits in any .py file: the product was removed in 5.x.
```

Detection concerns source calls, not the installed SDK version, current API success, configured credentials, or field correctness. Azure Document Intelligence, Mindee, and Veryfi are cloud APIs; the auditor never contacts them. The accepted product carries certificate type, heat number, and norm (the certification standard). It has no supplier name, customer name, material grade, chemical composition, or mechanical properties field. Other field sets require other routes; this checker checks the product call only.

Generic routes are attribute calls on any base or imported names, including aliases, with exactly one of these names. Bare unimported name calls do not count.

```text
extract_material_certificate
parse_material_certificate
extract_material_certificates
parse_material_certificates
extract_mill_test_certificate
parse_mill_test_certificate
extract_material_test_certificate
parse_material_test_certificate
extract_material_test_certificates
parse_material_test_certificates
material_certificate_extraction
material_certificate_extractor
material_certificate_parser
mill_test_certificate_extraction
mill_test_certificate_extractor
mill_test_certificate_parser
material_test_certificate_extraction
material_test_certificate_extractor
material_test_certificate_parser
extract_material_certificate_data
parse_material_certificate_data
material_certificate_scan
material_certificate_scanner
scan_material_certificate
```

## Limitations

Static pattern matching is not semantic judgement. Dead code counts; unsupported alias chains are missed. Exact phrases and denial handling depend on the fixed lists. A listed generic call can parse manually typed text and still count. A bare string parser with no listed call does not count. Subprocess wrappers invoking the Mindee CLI, Veryfi CLI, or any other external command do not count.

```text
The broad mill test certificate extraction / extract mill test certificates /
mill test certificate parsing / mill test certificate parser wording can refer
to records merely stored, displayed, or tracked in archives or supplier records.
Material test certificate extraction / extract material test certificate /
material test certificate parsing / material test certificate parser wording
can describe templates or rendered certificates instead of field extraction.
Material certificate scanning / scan material certificate can mean photography
or raw OCR. Material certificate parsing / material certificate parser can
mean formatted text or keyword highlighting. The phrases trigger the audit;
only source evidence decides the result.
```

Other Mindee products are excluded, including all of these:

```text
InvoiceV4 ReceiptV5 PassportV1 FinancialDocumentV1 BankCheckV1
BankAccountDetailsV1 BankAccountDetailsV2 PayslipV2 PayslipV3
NutritionFactsLabelV1 HealthcareCardV1 BusinessCardV1 CustomV1 GeneratedV1
BillOfLadingV1 ResumeV1 DeliveryNoteV1 DriverLicenseV1 IdCardV1
InternationalIdV2 CarteGriseV1 EnergyBillV1 BarcodeReaderV1 CropperV1
```

Barcode reading is a different operation even when a certificate carries an identifier. Plain text, OCR, CSV, spreadsheet, and table operations alone do not count. Handwritten re.search or re.findall on OCR text followed by manual field assembly is missed without a listed call. Imports, comments, strings, references without calls, and client construction alone do not count.

There is no Azure route for any model identifier: the Learn v4.0 GA model overview checked on 2026-11-14 has no corresponding model. No begin_analyze_document call counts. There is no Veryfi route of any kind: SDK 5.1.0 checked on 2026-11-14 has zero occurrences of "material" in its source, and its documents APIs share a generic endpoint across document types. Invented methods do not count either.

```text
Veryfi's generic endpoint is https://api.veryfi.com/api/v8/partner/documents.
process_material_certificate_document and process_material_certificate_document_url
are not SDK methods and do not count.
```

Google Document AI has no corresponding processor (processor list checked on 2026-11-14); process_document and batch_process_documents with any processor are excluded. Eden AI has no corresponding parser model, so universal-ai calls with any model identifier are excluded. Its OCR parsers are financial_parser, invoice_parser, receipt_parser, resume_parser, and identity_parser. LlamaParse is generative with no fixed fingerprint. Nanonets, Docsumo, ABBYY Vantage, Rossum, Klippa, Parseur, Extend, and Mindee v2 use opaque or configurable model, skill, queue, template, or workflow IDs, or a generic upload configured outside the call. None count. Textract has no corresponding operation: analyze_document, analyze_expense, analyze_id, start_document_analysis, and get_expense_analysis are generic document, expense, and identity analysis and do not count.

A generic certificate call with no material qualifier could describe any certificate. A certificate of conformity attests compliance but is a different document; a safety data sheet describes hazards and handling instead of certification test results. Report-named calls describe different documents from certificates. These calls are excluded:

```text
extract_certificate / parse_certificate / certificate_extraction
extract_certificate_of_conformity / extract_material_safety_data_sheet
extract_mill_test_report / extract_material_test_report
```

The following topics are outside the phrase vocabulary. Single field values can be lookups on existing data; composition and mechanical properties differ from the accepted panel. Plain text is a different output; templates and forms create documents; verification checks records instead of pulling fields. Conformity certificates, safety data sheets, and test reports are different documents.

```text
extract heat number / heat number extraction / extract norm / norm extraction
extract chemical composition / composition extraction / extract mechanical properties
extract material certificate text / extract text from material certificates
material certificate template / material certificate form
material certificate verification / certificate verification
certificate of conformity extraction / extract certificates of conformity
material safety data sheet extraction / extract material safety data sheets
material test report extraction / extract material test reports
```

Other document families are outside this check: invoices, receipts, identity documents, checks, bank statements, tax forms, pay stubs, insurance cards, business cards, credit cards, contracts, mortgages, resumes, bills of lading, delivery notes, vehicle registrations, energy bills, marriage certificates, bank account details (RIB), and nutrition facts labels. Their claims and evidence alone do not establish the checked capability.

## Fixed phrase vocabulary

Positive phrases (50):

```text
material certificate extraction
extract material certificates
extracts material certificates
extracting material certificates
extract material certificate
extracts material certificate
extracting material certificate
material certificate parsing
material certificate parser
parse material certificates
parses material certificates
parse material certificate
parses material certificate
material certificate scanning
material certificate scanner
scan material certificates
scans material certificates
scan material certificate
scans material certificate
mill test certificate extraction
extract mill test certificates
extracts mill test certificates
extracting mill test certificates
mill test certificate parsing
mill test certificate parser
parse mill test certificates
parses mill test certificates
mill test certificate scanning
mill test certificate scanner
scan mill test certificates
scans mill test certificates
material test certificate extraction
extract material test certificates
extracts material test certificates
extracting material test certificates
extract material test certificate
extracts material test certificate
extracting material test certificate
material test certificate parsing
material test certificate parser
parse material test certificates
parses material test certificates
parse material test certificate
parses material test certificate
material test certificate scanning
material test certificate scanner
scan material test certificates
scans material test certificates
scan material test certificate
scans material test certificate
```

Denial phrases (24):

```text
no material certificate extraction
does not extract material certificates
does not extract material certificate
does not support material certificate extraction
without material certificate extraction
no material certificate parser
does not parse material certificates
does not parse material certificate
no mill test certificate extraction
does not extract mill test certificates
does not support mill test certificate extraction
without mill test certificate extraction
no mill test certificate parser
does not parse mill test certificates
no material test certificate extraction
does not extract material test certificates
does not extract material test certificate
does not support material test certificate extraction
without material test certificate extraction
no material test certificate parser
does not parse material test certificates
does not parse material test certificate
no material certificate scanner
material certificate extraction not supported
```

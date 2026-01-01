from src.ingestion.commission import compute_expected_for_upload_dynamic, insert_expected_rows
rows = compute_expected_for_upload_dynamic(10)
print('expected rows:', len(rows))
print('inserted:', insert_expected_rows(rows))

# Allammedica Database Schema Analysis Summary

## Overview
Complete analysis of the allammedica healthcare database with 1007+ tables, focusing on 21 core healthcare entities, 2 views, and 71 relationships.

## Files Generated
1. **`database_schema.json`** - Core healthcare tables schema
2. **`enhanced_database_schema.json`** - Complete analysis with views and graph structure
3. **`generate_healthcare_schema.py`** - Schema extraction tool
4. **`analyze_views_and_relationships.py`** - Relationship analysis tool

## Core Healthcare Tables (21)

### Patient & Administrative
- **`pasien`** (36 cols, 9 FKs) - Patient master records
- **`reg_periksa`** (19 cols, 4 FKs) - Patient registrations/visits
- **`penjab`** (7 cols) - Payment methods/Insurance types
- **`poliklinik`** (5 cols) - Clinic departments

### Clinical Staff
- **`dokter`** (14 cols, 2 FKs) - Doctor information with specialization links

### Infrastructure
- **`bangsal`** (3 cols) - Hospital wards
- **`kamar`** (6 cols, 1 FK) - Rooms
- **`kamar_inap`** (12 cols, 2 FKs) - Inpatient room assignments

### Clinical Data
- **`penyakit`** (6 cols, 1 FK) - Disease/ICD codes
- **`diagnosa_pasien`** (5 cols, 2 FKs) - Patient diagnoses
- **`rawat_jl_dr`** (12 cols, 3 FKs) - Outpatient treatments
- **`rawat_inap_dr`** (11 cols, 3 FKs) - Inpatient treatments

### Diagnostics
- **`periksa_lab`** (17 cols, 5 FKs) - Laboratory examinations
- **`periksa_radiologi`** (24 cols, 5 FKs) - Radiology examinations

### Pharmacy
- **`obat_racikan`** (9 cols, 2 FKs) - Medication compounds
- **`resep_dokter`** (4 cols, 2 FKs) - Doctor prescriptions

### Procedures
- **`operasi`** (57 cols, 25 FKs) - Surgical procedures (most complex table)

### External Systems
- **`rujuk`** (10 cols, 2 FKs) - Patient referrals
- **`bridging_sep`** (52 cols, 1 FK) - BPJS insurance integration

### Billing
- **`nota_jalan`** (4 cols, 1 FK) - Outpatient billing
- **`nota_inap`** (5 cols, 1 FK) - Inpatient billing

## Database Views (2)

### `pasien_clean`
- **Purpose**: Cleaned patient data view
- **Definition**: `SELECT no_rkm_medis, nm_pasien, no_ktp FROM pasien...`
- **Use**: Data quality and reporting

### `view_resume_pasien`
- **Purpose**: Patient resume/summary view
- **Definition**: `SELECT no_rawat, kd_dokter, keluhan_utama FROM resume...`
- **Use**: Clinical summaries and reporting

## Key Relationships (71 total)

### Patient-Centric (no_rkm_medis)
```
pasien → reg_periksa → diagnosa_pasien
       → rawat_jl_dr/rawat_inap_dr
       → periksa_lab/periksa_radiologi
       → operasi
       → rujuk
```

### Registration-Centric (no_rawat)
```
reg_periksa → diagnosa_pasien
           → rawat_jl_dr/rawat_inap_dr
           → periksa_lab/periksa_radiologi
           → operasi
           → nota_jalan/nota_inap
```

### Clinical Workflow
```
pasien → reg_periksa → dokter → diagnosa_pasien
                             → rawat_jl_dr
                             → resep_dokter → obat_racikan
```

## Graph Database Structure

### Nodes (21)
- **Patient Domain**: `pasien` (primary hub)
- **Clinical Domain**: `diagnosa_pasien`, `penyakit`, `operasi`, `periksa_*`
- **Administrative**: `reg_periksa`, `nota_*`, `bridging_sep`
- **Staff**: `dokter`
- **Infrastructure**: `kamar*`, `bangsal`, `poliklinik`
- **Pharmacy**: `obat_racikan`, `resep_dokter`

### Edges (71)
- **Foreign Key Relationships**: Direct table-to-table links
- **Hub Pattern**: `pasien` and `reg_periksa` are central hubs
- **Workflow Chains**: Registration → Treatment → Billing

## Statistics
- **Total Tables in DB**: 1,007
- **Core Tables Analyzed**: 21
- **Total Columns**: 318
- **Foreign Key Relationships**: 71
- **Average Columns per Table**: 15.1
- **Most Complex Table**: `operasi` (57 columns, 25 FKs)
- **Database Views**: 2

## Recommendations for Graph Database

### 1. **Node Categories**
```json
{
  "patient": ["pasien"],
  "clinical": ["diagnosa_pasien", "penyakit", "operasi", "periksa_lab", "periksa_radiologi"],
  "administrative": ["reg_periksa", "nota_jalan", "nota_inap", "bridging_sep"],
  "staff": ["dokter"],
  "infrastructure": ["kamar_inap", "bangsal", "poliklinik"],
  "pharmacy": ["obat_racikan", "resep_dokter"]
}
```

### 2. **Key Relationship Types**
- **HAS_REGISTRATION**: `pasien → reg_periksa`
- **DIAGNOSED_WITH**: `reg_periksa → diagnosa_pasien → penyakit`
- **TREATED_BY**: `reg_periksa → dokter`
- **UNDERWENT**: `reg_periksa → operasi/periksa_lab/periksa_radiologi`
- **PRESCRIBED**: `dokter → resep_dokter → obat_racikan`
- **BILLED_AS**: `reg_periksa → nota_jalan/nota_inap`

### 3. **Query Generation Patterns**
- **Patient Journey**: Follow `no_rkm_medis` through `reg_periksa` to all clinical activities
- **Clinical Workflow**: Track `no_rawat` from registration to discharge
- **Doctor Workload**: Aggregate activities by `kd_dokter`
- **Department Analytics**: Group by `kd_poli` or `bangsal`

## Ready for Implementation
The schema is now comprehensive enough to:
1. **Generate intelligent SQL queries** using graph traversal
2. **Understand semantic relationships** between healthcare entities
3. **Support complex healthcare workflows** and reporting
4. **Enable natural language query processing** with proper context

The enhanced schema provides the foundation for your graph database approach to MySQL query generation.
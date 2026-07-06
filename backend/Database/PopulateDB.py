import os
import asyncio
import asyncpg
from faker import Faker
import random
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

faker = Faker()

# Get the connection string from the environment variable
connection_string = os.getenv("DATABASE_URL")
if not connection_string:
    raise ValueError("DATABASE_URL environment variable is not set")

# --- Configuration for Data Generation ---
NUM_HOSPITALS = 3
NUM_DEPARTMENTS_PER_HOSPITAL_AVG = 4
NUM_STAFF_PER_HOSPITAL_AVG = 20
NUM_DOCTORS_PER_DEPARTMENT_AVG = 3
NUM_WARDS_PER_HOSPITAL_AVG = 3
NUM_BEDS_PER_WARD_AVG = 10

NUM_PATIENTS = 200
NUM_INS_PROVIDERS = 15
NUM_MEDICATIONS = 200

NUM_APPOINTMENTS = 400
NUM_VISITS_TARGET = 600
NUM_TREATMENTS_TARGET = 500
NUM_BILLS_TARGET = 600
NUM_BED_ASSIGNMENTS_TARGET = 100

# --- Configuration for Data Generation Control ---
# Set to False to skip schema creation (if it already exists)
CREATE_SCHEMA_AND_TABLES = True

# Set to False to skip insertion for a specific table
INSERT_HOSPITALS = True
INSERT_DEPARTMENTS = True
INSERT_STAFF = True
INSERT_DOCTORS = True  # Also updates department head doctors
INSERT_PATIENTS = True
INSERT_INSURANCE_PROVIDERS = True
INSERT_INSURANCE_POLICIES = True  # Depends on patients, providers
INSERT_WARDS = True  # Depends on hospitals
INSERT_BEDS = True  # Depends on wards
INSERT_MEDICATIONS = True
INSERT_APPOINTMENTS = True  # Depends on patients, doctors, departments
INSERT_VISITS = True  # Depends on patients, doctors, departments, appointments (optional for app_id)
INSERT_BED_ASSIGNMENTS = True  # Depends on patients, beds, visits
INSERT_MEDICAL_RECORDS = True  # Depends on visits, patients
INSERT_TREATMENTS = True  # Depends on visits
INSERT_PRESCRIPTIONS = True  # Depends on visits, doctors, patients
INSERT_PRESCRIPTION_MEDICATIONS = True  # Depends on prescriptions, medications
INSERT_BILLS = True  # Depends on patients, visits (optional)
INSERT_BILL_ITEMS = (
    True  # Depends on bills, treatments (optional), prescription_medications (optional)
)

# Note on selective insertion:
# If you set a flag for a prerequisite table to False (e.g., INSERT_PATIENTS = False),
# and a subsequent table's flag is True (e.g., INSERT_APPOINTMENTS = True),
# the script will attempt to proceed. However, if the prerequisite IDs (e.g., patient_ids)
# are not available (because they weren't inserted in this run), the dependent table
# insertion will likely be skipped due to missing foreign key data. This is because
# the script relies on ID lists populated during the same run.
#
# To populate specific tables (e.g., 'visits') when prerequisites already exist in the DB
# (e.g., from a previous run or external population):
# 1. Set CREATE_SCHEMA_AND_TABLES = False.
# 2. Set INSERT_ flags for all prerequisite tables to False.
# 3. Set INSERT_ flag for the target table(s) to True.
# 4. CRITICAL: This script version DOES NOT automatically fetch existing IDs from the database
#    if their corresponding INSERT_ flag is False. If `patient_ids`, `doctor_ids`, etc.,
#    are needed for `INSERT_VISITS = True` but `INSERT_PATIENTS = False`, these ID lists
#    will be empty, and visit insertion will likely fail or be skipped.
#    You would need to modify the script to fetch these IDs from the DB if you
#    require this "populate only specific tables using existing DB data" behavior.


def random_date(
    start_date_str, end_date_str="today"
):  # Corrected end_date_str default for clarity
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    end = (
        datetime.now()
        if end_date_str == "today"
        else datetime.strptime(end_date_str, "%Y-%m-%d")
    )
    return faker.date_between(start_date=start, end_date=end)


def random_datetime(start_offset_days=-365 * 5, end_offset_days=0):
    base_dt = datetime.now(timezone.utc)
    start_dt = base_dt + timedelta(days=start_offset_days)
    end_dt = base_dt + timedelta(days=end_offset_days)
    if start_dt > end_dt:
        start_dt = end_dt - timedelta(days=1)
    return faker.date_time_between(
        start_date=start_dt, end_date=end_dt, tzinfo=timezone.utc
    )


async def create_schema(conn):
    """Create database schema by executing SQL from create.sql file"""
    schema_file_path = os.path.join(os.path.dirname(__file__), "create.sql")
    try:
        with open(schema_file_path, "r") as file:
            schema_sql_content = file.read()
        statements = []
        current_statement = ""
        for line in schema_sql_content.splitlines():
            line_content = line.strip()
            if not line_content or line_content.startswith("--"):
                continue
            line_content = line_content.split("--", 1)[0].strip()
            if not line_content:
                continue
            current_statement += line_content + "\n"
            if line_content.endswith(";"):
                statements.append(current_statement.strip())
                current_statement = ""
        if current_statement.strip():
            statements.append(current_statement.strip())

        print(f"Creating database schema from: {schema_file_path}")
        print(f"Found {len(statements)} SQL statements to execute.")
        if not statements:
            print(
                "WARNING: No SQL statements were parsed from the schema file. Schema will not be created."
            )
            return
        async with conn.transaction():
            for i, statement_sql in enumerate(statements):
                if statement_sql:
                    try:
                        printable_statement = " ".join(statement_sql.splitlines())[:100]
                        print(
                            f"Executing statement {i+1}/{len(statements)}: {printable_statement}..."
                        )
                        await conn.execute(statement_sql)
                    except Exception as e:
                        print(
                            f"❌ Error executing statement {i+1} (schema transaction will be rolled back): {e}"
                        )
                        print(f"Statement was: {statement_sql}")
                        raise
        print(
            "✓ Database schema created successfully (or transaction rolled back on error)."
        )
    except FileNotFoundError:
        print(
            f"❌ Schema file not found at {schema_file_path}. Please ensure it exists."
        )
        raise
    except Exception as e:
        print(f"❌ Error during schema creation: {e}")
        import traceback

        traceback.print_exc()
        raise


async def insert_records(
    conn, table, columns, values, return_ids=False, id_column="id"
):
    """Insert multiple records into a table. Optionally return IDs."""
    if not values:
        return []
    placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
    base_query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    inserted_ids = []
    async with conn.transaction():
        for value_tuple in values:
            try:
                if return_ids:
                    query = f"{base_query} RETURNING {id_column}"
                    record_id = await conn.fetchval(query, *value_tuple)
                    inserted_ids.append(record_id)
                else:
                    await conn.execute(base_query, *value_tuple)
            except Exception as e:
                print(f"❌ Error inserting into {table} for values {value_tuple}: {e}")
                raise
    return inserted_ids


async def main():
    pool = await asyncpg.create_pool(connection_string)

    # Initialize ID lists and data maps
    hospital_ids = []
    department_ids = []
    staff_ids = []
    doctor_ids = []
    doctors_data = []  # To store tuple data for head doctor linking
    patient_ids = []
    ins_provider_ids = []
    policy_ids = []
    ward_ids = []
    bed_ids = []
    medication_ids = []
    medications_data = []  # To store tuple data for bill items
    appointment_ids = []
    appointments_data = []  # To store tuple data for visit linking
    visit_ids = []
    visits_data = []  # To store tuple data for linking
    visit_details_map = {}
    bed_assignment_ids = []
    med_record_ids = []
    treatment_ids = []
    treatments_data = []  # To store tuple data for linking
    treatment_details_map = {}
    prescription_ids = []
    prescriptions_data_tuples = []  # To store tuple data for linking
    prescription_medication_ids = []
    prescription_med_data_collector = []  # To store tuple data for linking
    pm_details_map = {}
    bill_ids_generated = []
    bills_data = []  # To store tuple data for linking
    bill_info_map_for_items = {}
    bill_item_ids = []

    try:
        async with pool.acquire() as conn:
            version = await conn.fetchval("SELECT version();")
            print(f"Connected to PostgreSQL: {version}")

            if CREATE_SCHEMA_AND_TABLES:
                await create_schema(conn)
            else:
                print("Skipping schema creation as per CREATE_SCHEMA_AND_TABLES=False.")

            print("\nStarting data population (based on configuration flags)...")

            # Hospitals
            if INSERT_HOSPITALS:
                print("Inserting hospitals...")
                hospitals_data_tuples = []
                for _ in range(NUM_HOSPITALS):
                    hospitals_data_tuples.append(
                        (
                            faker.company() + " Hospital",
                            faker.address(),
                            faker.phone_number()[:30],
                            faker.unique.email(),
                            faker.url(),
                            random_date("1950-01-01", "2010-01-01"),
                        )
                    )
                faker.unique.clear()
                hospital_ids = await insert_records(
                    conn,
                    "hospitals",
                    [
                        "name",
                        "address",
                        "phone_number",
                        "email",
                        "website",
                        "established_date",
                    ],
                    hospitals_data_tuples,
                    return_ids=True,
                )
                print(f"✓ Inserted {len(hospital_ids)} hospitals")
            else:
                print("Skipping Hospitals insertion.")

            # Departments
            if INSERT_DEPARTMENTS:
                print("Inserting departments...")
                departments_data_tuples = []
                if (
                    not hospital_ids
                    and NUM_DEPARTMENTS_PER_HOSPITAL_AVG > 0
                    and NUM_HOSPITALS > 0
                ):  # Warn if trying to insert but no hospital_ids
                    print(
                        "WARNING: Cannot insert departments without hospital_ids. Please enable INSERT_HOSPITALS or ensure hospitals exist in DB and hospital_ids are fetched."
                    )
                for h_id in hospital_ids:
                    for _ in range(
                        random.randint(
                            max(1, NUM_DEPARTMENTS_PER_HOSPITAL_AVG - 2),
                            NUM_DEPARTMENTS_PER_HOSPITAL_AVG + 2,
                        )
                    ):
                        departments_data_tuples.append(
                            (
                                faker.job()
                                .split(",")[0]
                                .replace(" specialist", "")
                                .replace(" consultant", "")
                                .title()
                                + " Department",
                                h_id,
                                faker.bs(),
                            )
                        )
                if departments_data_tuples:
                    department_ids = await insert_records(
                        conn,
                        "departments",
                        [
                            "name",
                            "hospital_id",
                            "description",
                        ],
                        departments_data_tuples,
                        return_ids=True,
                    )
                    print(f"✓ Inserted {len(department_ids)} departments")
                elif (
                    hospital_ids
                ):  # hospital_ids exist but no departments were generated (e.g. NUM_DEPARTMENTS_PER_HOSPITAL_AVG = 0)
                    print("No departments generated for existing hospitals.")
                else:  # No hospital_ids and no departments generated
                    print(
                        "Skipping department insertion as no hospital_ids are available."
                    )

            else:
                print("Skipping Departments insertion.")

            # Staff
            if INSERT_STAFF:
                print("Inserting staff...")
                staff_data_tuples = []
                department_id_choices = department_ids if department_ids else [None]
                if None not in department_id_choices and department_ids:
                    department_id_choices_for_staff = department_ids + [None]
                else:
                    department_id_choices_for_staff = department_id_choices

                if (
                    not hospital_ids
                    and NUM_STAFF_PER_HOSPITAL_AVG > 0
                    and NUM_HOSPITALS > 0
                ):
                    print(
                        "WARNING: Cannot insert staff without hospital_ids. Please enable INSERT_HOSPITALS or ensure hospitals exist in DB and hospital_ids are fetched."
                    )

                for h_id in hospital_ids:
                    for _ in range(
                        random.randint(
                            max(1, NUM_STAFF_PER_HOSPITAL_AVG - 5),
                            NUM_STAFF_PER_HOSPITAL_AVG + 10,
                        )
                    ):
                        staff_data_tuples.append(
                            (
                                faker.name(),
                                random.choice(
                                    [
                                        "Nurse",
                                        "Technician",
                                        "Administrator",
                                        "Clerk",
                                        "Support Staff",
                                        "Janitor",
                                        "Security",
                                    ]
                                ),
                                h_id,
                                (
                                    random.choice(department_id_choices_for_staff)
                                    if department_id_choices_for_staff
                                    and any(
                                        department_id_choices_for_staff
                                    )  # Ensure not just [None]
                                    else None
                                ),
                                round(random.uniform(30000, 90000), 2),
                                random_date("2000-01-01", "today"),
                                faker.phone_number()[:30],
                                faker.unique.email(),
                                faker.address(),
                            )
                        )
                faker.unique.clear()
                if staff_data_tuples:
                    staff_ids = await insert_records(
                        conn,
                        "staff",
                        [
                            "name",
                            "role",
                            "hospital_id",
                            "department_id",
                            "salary",
                            "hire_date",
                            "phone",
                            "email",
                            "address",
                        ],
                        staff_data_tuples,
                        return_ids=True,
                    )
                    print(f"✓ Inserted {len(staff_ids)} staff")
                elif hospital_ids:
                    print("No staff generated for existing hospitals.")
                else:
                    print("Skipping staff insertion as no hospital_ids are available.")
            else:
                print("Skipping Staff insertion.")

            # Doctors
            if INSERT_DOCTORS:
                print("Inserting doctors...")
                # doctors_data already initialized as []
                if (
                    not department_ids
                    and NUM_DOCTORS_PER_DEPARTMENT_AVG > 0
                    and (NUM_DEPARTMENTS_PER_HOSPITAL_AVG > 0 and NUM_HOSPITALS > 0)
                ):
                    print(
                        "WARNING: No departments available to assign doctors. Please enable INSERT_DEPARTMENTS or ensure departments exist and department_ids are fetched."
                    )
                else:
                    for dept_id in department_ids:
                        for _ in range(
                            random.randint(
                                max(1, NUM_DOCTORS_PER_DEPARTMENT_AVG - 1),
                                NUM_DOCTORS_PER_DEPARTMENT_AVG + 1,
                            )
                        ):
                            doctors_data.append(  # Appending to the global doctors_data
                                (
                                    faker.name(),
                                    faker.job().split(",")[0].title(),
                                    dept_id,
                                    faker.phone_number()[:30],
                                    faker.unique.email(),
                                    faker.unique.bothify(text="LIC-????####"),
                                    random.randint(0, 35),
                                )
                            )
                faker.unique.clear()
                if doctors_data:
                    doctor_ids = await insert_records(
                        conn,
                        "doctors",
                        [
                            "name",
                            "specialization",
                            "department_id",
                            "phone",
                            "email",
                            "license_number",
                            "years_of_experience",
                        ],
                        doctors_data,  # Use the populated global doctors_data
                        return_ids=True,
                    )
                    print(f"✓ Inserted {len(doctor_ids)} doctors")

                    # Update departments with head_doctor_id (only if doctors were inserted)
                    print("Updating departments with head doctors...")
                    doctors_by_dept = {}
                    for i, doc_data_tuple in enumerate(
                        doctors_data
                    ):  # Iterate over the collected doctors_data
                        doc_id = doctor_ids[i]
                        dept_id_for_doc = doc_data_tuple[2]
                        if dept_id_for_doc not in doctors_by_dept:
                            doctors_by_dept[dept_id_for_doc] = []
                        doctors_by_dept[dept_id_for_doc].append(doc_id)

                    updates = 0
                    async with conn.transaction():
                        for (
                            dept_id_to_update
                        ) in department_ids:  # Iterate over existing department_ids
                            if (
                                dept_id_to_update in doctors_by_dept
                                and doctors_by_dept[dept_id_to_update]
                            ):
                                head_doc_id = random.choice(
                                    doctors_by_dept[dept_id_to_update]
                                )
                                await conn.execute(
                                    "UPDATE departments SET head_doctor_id = $1 WHERE id = $2",
                                    head_doc_id,
                                    dept_id_to_update,
                                )
                                updates += 1
                    print(f"✓ Updated {updates} departments with head doctors.")
                elif department_ids:
                    print("No doctors generated for existing departments.")
                else:
                    print("Skipping doctor insertion as no departments are available.")
            else:
                print("Skipping Doctors insertion (and head doctor updates).")

            # Patients
            if INSERT_PATIENTS:
                print("Inserting patients...")
                patients_data_tuples = []
                for _ in range(NUM_PATIENTS):
                    patients_data_tuples.append(
                        (
                            faker.name(),
                            faker.date_of_birth(minimum_age=0, maximum_age=100),
                            random.choice(
                                ["Male", "Female", "Other", "Prefer not to say"]
                            ),
                            faker.phone_number()[:30],
                            faker.unique.email(),
                            faker.address(),
                            random.choice(
                                ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", None]
                            ),
                            (
                                faker.text(max_nb_chars=40)
                                if random.random() < 0.3
                                else None
                            ),
                        )
                    )
                faker.unique.clear()
                patient_ids = await insert_records(
                    conn,
                    "patients",
                    [
                        "name",
                        "date_of_birth",
                        "gender",
                        "phone",
                        "email",
                        "address",
                        "blood_type",
                        "allergies",
                    ],
                    patients_data_tuples,
                    return_ids=True,
                )
                print(f"✓ Inserted {len(patient_ids)} patients")
            else:
                print("Skipping Patients insertion.")

            # Insurance Providers
            if INSERT_INSURANCE_PROVIDERS:
                print("Inserting insurance providers...")
                ins_providers_data_tuples = []
                for _ in range(NUM_INS_PROVIDERS):
                    ins_providers_data_tuples.append(
                        (
                            faker.unique.company() + " Health",
                            faker.phone_number()[:30],
                            faker.address(),
                            faker.email(),
                        )
                    )
                faker.unique.clear()
                ins_provider_ids = await insert_records(
                    conn,
                    "insurance_providers",
                    ["name", "phone_number", "address", "email"],
                    ins_providers_data_tuples,
                    return_ids=True,
                )
                print(f"✓ Inserted {len(ins_provider_ids)} insurance providers")
            else:
                print("Skipping Insurance Providers insertion.")

            # Insurance Policies
            if INSERT_INSURANCE_POLICIES:
                if patient_ids and ins_provider_ids:
                    print("Inserting insurance policies...")
                    policies_data_tuples = []
                    for p_id in patient_ids:
                        if random.random() < 0.8:
                            num_policies = random.randint(1, 2)
                            for _ in range(num_policies):
                                start_date = random_date("2020-01-01", "today")
                                policies_data_tuples.append(
                                    (
                                        p_id,
                                        random.choice(ins_provider_ids),
                                        faker.unique.bothify(text="POL-#######??"),
                                        json.dumps(
                                            {
                                                "type": random.choice(
                                                    [
                                                        "Basic",
                                                        "Comprehensive",
                                                        "Family",
                                                        "Individual",
                                                    ]
                                                ),
                                                "deductible": random.randint(50, 1500),
                                                "max_annual_limit": random.randint(
                                                    5000, 250000
                                                ),
                                                "co_pay_pct": random.randint(10, 30),
                                            }
                                        ),
                                        start_date,
                                        start_date
                                        + timedelta(
                                            days=random.randint(365, 365 * 3 + 180)
                                        ),
                                    )
                                )
                    faker.unique.clear()
                    if policies_data_tuples:
                        policy_ids = await insert_records(
                            conn,
                            "insurance_policies",
                            [
                                "patient_id",
                                "provider_id",
                                "policy_number",
                                "coverage_details",
                                "start_date",
                                "end_date",
                            ],
                            policies_data_tuples,
                            return_ids=True,
                        )
                        print(f"✓ Inserted {len(policy_ids)} insurance policies")
                    else:
                        print(
                            "No insurance policies generated (possibly no patients or providers, or low random chance)."
                        )
                else:
                    print(
                        "Skipping insurance policies: Missing patient_ids or ins_provider_ids."
                    )
            else:
                print("Skipping Insurance Policies insertion.")

            # Wards
            if INSERT_WARDS:
                if hospital_ids:
                    print("Inserting wards...")
                    wards_data_tuples = []
                    department_id_choices_for_ward = (
                        department_ids if department_ids else [None]
                    )
                    if None not in department_id_choices_for_ward and department_ids:
                        department_id_choices_for_ward.append(None)

                    for h_id in hospital_ids:
                        for _ in range(
                            random.randint(
                                max(1, NUM_WARDS_PER_HOSPITAL_AVG - 1),
                                NUM_WARDS_PER_HOSPITAL_AVG + 1,
                            )
                        ):
                            wards_data_tuples.append(
                                (
                                    f"Ward {faker.random_uppercase_letter()}-{random.randint(1,10)} ({random.choice(['General', 'Surgical', 'Maternity', 'Pediatric', 'ICU'])})",
                                    h_id,
                                    (
                                        random.choice(department_id_choices_for_ward)
                                        if department_id_choices_for_ward
                                        and any(
                                            d_id
                                            for d_id in department_id_choices_for_ward
                                            if d_id is not None
                                        )  # check if there are actual depts
                                        else None
                                    ),
                                    random.randint(
                                        max(5, int(NUM_BEDS_PER_WARD_AVG * 0.5)),
                                        int(NUM_BEDS_PER_WARD_AVG * 1.5),
                                    ),
                                )
                            )
                    if wards_data_tuples:
                        ward_ids = await insert_records(
                            conn,
                            "wards",
                            ["name", "hospital_id", "department_id", "capacity"],
                            wards_data_tuples,
                            return_ids=True,
                        )
                        print(f"✓ Inserted {len(ward_ids)} wards")
                    else:
                        print("No wards generated for existing hospitals.")
                else:
                    print("Skipping wards: Missing hospital_ids.")
            else:
                print("Skipping Wards insertion.")

            # Beds
            if INSERT_BEDS:
                if ward_ids:
                    print("Inserting beds...")
                    beds_data_tuples = []
                    for w_id in ward_ids:
                        num_beds_in_ward = random.randint(
                            max(1, NUM_BEDS_PER_WARD_AVG - 5), NUM_BEDS_PER_WARD_AVG + 5
                        )
                        for i in range(max(1, num_beds_in_ward)):
                            beds_data_tuples.append(
                                (
                                    f"B{i+1:03d}",
                                    w_id,
                                    "available",
                                    random.choice(
                                        [
                                            "Standard",
                                            "ICU",
                                            "Pediatric",
                                            "Semi-Private",
                                            "Private",
                                        ]
                                    ),
                                )
                            )
                    if beds_data_tuples:
                        bed_ids = await insert_records(
                            conn,
                            "beds",
                            ["bed_number", "ward_id", "status", "bed_type"],
                            beds_data_tuples,
                            return_ids=True,
                        )
                        print(f"✓ Inserted {len(bed_ids)} beds")
                    else:
                        print("No beds generated for existing wards.")
                else:
                    print("Skipping beds: Missing ward_ids.")
            else:
                print("Skipping Beds insertion.")

            # Medications
            if INSERT_MEDICATIONS:
                print("Inserting medications...")
                # medications_data already initialized as []
                for _ in range(NUM_MEDICATIONS):
                    medications_data.append(
                        (
                            faker.word().capitalize()
                            + " "
                            + random.choice(
                                ["XR", "SR", "Generic", "Forte", "Plus", "Pediatric"]
                            ),
                            faker.text(max_nb_chars=150),
                            faker.company(),
                            random.choice(
                                [
                                    "Tablet",
                                    "Capsule",
                                    "Syrup",
                                    "Injection",
                                    "Ointment",
                                    "Drops",
                                    "Inhaler",
                                    "Patch",
                                ]
                            ),
                            f"{random.randint(1,1000)}{random.choice(['mg', 'ml', 'mcg', 'IU', 'g'])}",
                            round(random.uniform(0.5, 350.0), 2),
                        )
                    )
                medication_ids = await insert_records(
                    conn,
                    "medications",
                    [
                        "name",
                        "description",
                        "manufacturer",
                        "dosage_form",
                        "strength",
                        "unit_price",
                    ],
                    medications_data,  # use global medications_data
                    return_ids=True,
                )
                print(f"✓ Inserted {len(medication_ids)} medications")
            else:
                print("Skipping Medications insertion.")

            # Appointments
            if INSERT_APPOINTMENTS:
                if patient_ids and doctor_ids and department_ids:
                    print("Inserting appointments...")
                    # appointments_data already initialized as []
                    doc_to_dept_map = {
                        doc_id: data[2]
                        for doc_id, data in zip(
                            doctor_ids, doctors_data
                        )  # doctors_data contains raw tuples
                    }

                    for _ in range(NUM_APPOINTMENTS):
                        p_id = random.choice(patient_ids)
                        doc_id = random.choice(doctor_ids)
                        dept_id = doc_to_dept_map.get(doc_id)
                        if not dept_id:
                            dept_id = random.choice(department_ids)  # Fallback

                        appointments_data.append(
                            (
                                p_id,
                                doc_id,
                                dept_id,
                                random_datetime(
                                    start_offset_days=-180, end_offset_days=90
                                ),
                                random.choice(
                                    [
                                        "scheduled",
                                        "completed",
                                        "cancelled",
                                        "no-show",
                                        "rescheduled",
                                    ]
                                ),
                                faker.sentence(nb_words=random.randint(3, 7)),
                                (
                                    faker.sentence(nb_words=random.randint(5, 15))
                                    if random.random() < 0.5
                                    else None
                                ),
                            )
                        )
                    if appointments_data:
                        appointment_ids = await insert_records(
                            conn,
                            "appointments",
                            [
                                "patient_id",
                                "doctor_id",
                                "department_id",
                                "appointment_datetime",
                                "status",
                                "reason",
                                "notes",
                            ],
                            appointments_data,  # Use global appointments_data
                            return_ids=True,
                        )
                        print(f"✓ Inserted {len(appointment_ids)} appointments")
                    else:
                        print("No appointments generated.")
                else:
                    print(
                        "Skipping appointments: Missing patient_ids, doctor_ids, or department_ids."
                    )
            else:
                print("Skipping Appointments insertion.")

            # Visits
            if INSERT_VISITS:
                if patient_ids and doctor_ids and department_ids:
                    print("Inserting visits...")
                    # visits_data already initialized
                    # visit_details_map already initialized
                    doc_to_dept_map = {
                        doc_id: data[2]
                        for doc_id, data in zip(doctor_ids, doctors_data)
                    }

                    # NOTE: Ensure these visit_type values are allowed by your 'visits_visit_type_check' constraint in create.sql
                    # The error you saw mentioned "Consultation" which is not generated here.
                    # If the error persists, check your schema and adjust these lists or your schema.
                    valid_appointment_based_visit_types = [
                        "OPD",
                        "Follow-up",
                        "Routine Checkup",
                        "In-patient Consult",
                    ]
                    valid_direct_visit_types = [
                        "Emergency",
                        "In-patient Consult",
                        "OPD",
                        "Follow-up",
                    ]

                    completed_or_past_app_details = []
                    if (
                        appointment_ids
                    ):  # appointments_data should be populated if appointment_ids exist
                        for i, app_id in enumerate(appointment_ids):
                            if i < len(appointments_data):  # Ensure index is valid
                                app_data_tuple = appointments_data[i]
                                app_status = app_data_tuple[4]
                                app_datetime = app_data_tuple[3]
                                if (
                                    app_status == "completed"
                                    or (
                                        app_status == "scheduled"
                                        and app_datetime < datetime.now(timezone.utc)
                                    )
                                    or (
                                        app_status == "rescheduled"
                                        and app_datetime < datetime.now(timezone.utc)
                                        and random.random() < 0.5
                                    )
                                ):
                                    completed_or_past_app_details.append(
                                        (
                                            app_id,
                                            app_data_tuple[0],  # p_id
                                            app_data_tuple[1],  # doc_id
                                            app_data_tuple[2],  # dept_id
                                            app_datetime,
                                        )
                                    )

                    num_visits_from_apps = 0
                    if completed_or_past_app_details:
                        num_visits_from_apps = min(
                            len(completed_or_past_app_details),
                            int(NUM_VISITS_TARGET * 0.7),
                        )
                        selected_apps_for_visits = random.sample(
                            completed_or_past_app_details, num_visits_from_apps
                        )

                        for (
                            app_id,
                            p_id,
                            doc_id,
                            dept_id,
                            app_datetime,
                        ) in selected_apps_for_visits:
                            visit_start = app_datetime + timedelta(
                                minutes=random.randint(-10, 10)
                            )
                            visit_end = visit_start + timedelta(
                                minutes=random.randint(15, 120)
                            )
                            visits_data.append(  # Add to global visits_data
                                (
                                    p_id,
                                    doc_id,
                                    dept_id,
                                    app_id,
                                    visit_start,
                                    visit_end,
                                    random.choice(valid_appointment_based_visit_types),
                                    faker.text(max_nb_chars=70),
                                    faker.text(max_nb_chars=70),
                                    faker.text(max_nb_chars=150),
                                )
                            )

                    num_direct_visits = NUM_VISITS_TARGET - len(visits_data)
                    for _ in range(max(0, num_direct_visits)):
                        p_id = random.choice(patient_ids)
                        doc_id = random.choice(doctor_ids)
                        dept_id = doc_to_dept_map.get(doc_id)
                        if not dept_id:
                            dept_id = (
                                random.choice(department_ids)
                                if department_ids
                                else None
                            )

                        visit_start = random_datetime(
                            start_offset_days=-730, end_offset_days=0
                        )
                        visit_end = visit_start + timedelta(
                            minutes=random.randint(20, 240)
                        )
                        visits_data.append(  # Add to global visits_data
                            (
                                p_id,
                                doc_id,
                                dept_id,
                                None,
                                visit_start,
                                visit_end,
                                random.choice(valid_direct_visit_types),
                                faker.text(max_nb_chars=80),
                                faker.text(max_nb_chars=80),
                                faker.text(max_nb_chars=180),
                            )
                        )
                    if visits_data:
                        visit_ids = await insert_records(
                            conn,
                            "visits",
                            [
                                "patient_id",
                                "doctor_id",
                                "department_id",
                                "appointment_id",
                                "visit_datetime_start",
                                "visit_datetime_end",
                                "visit_type",
                                "symptoms",
                                "diagnosis",
                                "notes",
                            ],
                            visits_data,  # Use global visits_data
                            return_ids=True,
                        )
                        print(f"✓ Inserted {len(visit_ids)} visits")
                        visit_details_map = {  # Populate global map
                            visit_ids[i]: visits_data[i] for i in range(len(visit_ids))
                        }
                    else:
                        print("No visits generated.")
                else:
                    print(
                        "Skipping visits: Missing patient_ids, doctor_ids, or department_ids."
                    )
            else:
                print("Skipping Visits insertion.")

            # Bed Assignments
            if INSERT_BED_ASSIGNMENTS:
                if (
                    patient_ids and bed_ids and visit_ids
                ):  # visit_details_map needs visit_ids
                    print("Inserting bed assignments...")
                    bed_assignments_data_tuples = []
                    available_beds_for_assignment = [
                        bid for bid in bed_ids if random.random() < 0.8
                    ]

                    in_patient_candidate_visits = []
                    for v_id in visit_ids:
                        if v_id in visit_details_map:
                            v_data = visit_details_map[v_id]
                            if (
                                v_data[6]
                                in [
                                    "Emergency",
                                    "In-patient Consult",
                                ]  # visit_type is index 6
                                and random.random() < 0.6
                            ):
                                in_patient_candidate_visits.append(v_id)
                        else:
                            print(
                                f"Warning: Visit ID {v_id} not found in visit_details_map for bed assignment."
                            )

                    num_assignments_to_make = min(
                        len(in_patient_candidate_visits),
                        len(available_beds_for_assignment),
                        NUM_BED_ASSIGNMENTS_TARGET,
                    )

                    if (
                        num_assignments_to_make > 0
                        and len(in_patient_candidate_visits) >= num_assignments_to_make
                        and len(available_beds_for_assignment)
                        >= num_assignments_to_make
                    ):
                        selected_visits_for_beds = random.sample(
                            in_patient_candidate_visits, num_assignments_to_make
                        )
                        selected_beds_for_assignment = random.sample(
                            available_beds_for_assignment, num_assignments_to_make
                        )

                        for i in range(num_assignments_to_make):
                            v_id = selected_visits_for_beds[i]
                            if v_id not in visit_details_map:
                                print(
                                    f"Warning: Visit ID {v_id} from sample not in visit_details_map. Skipping bed assignment."
                                )
                                continue
                            bed_id_to_assign = selected_beds_for_assignment[i]
                            visit_data = visit_details_map[v_id]
                            patient_id_for_assignment = visit_data[0]
                            admission_dt = visit_data[4]
                            discharge_dt = admission_dt + timedelta(
                                days=random.randint(1, 14),
                                hours=random.randint(0, 23),
                                minutes=random.randint(0, 59),
                            )

                            bed_assignments_data_tuples.append(
                                (
                                    patient_id_for_assignment,
                                    bed_id_to_assign,
                                    v_id,
                                    admission_dt,
                                    discharge_dt,
                                    (
                                        faker.sentence()
                                        if random.random() < 0.25
                                        else None
                                    ),
                                )
                            )
                    if bed_assignments_data_tuples:
                        bed_assignment_ids = await insert_records(
                            conn,
                            "bed_assignments",
                            [
                                "patient_id",
                                "bed_id",
                                "visit_id",
                                "admission_datetime",
                                "discharge_datetime",
                                "notes",
                            ],
                            bed_assignments_data_tuples,
                            return_ids=True,
                        )
                        print(f"✓ Inserted {len(bed_assignment_ids)} bed assignments")
                    else:
                        print("No bed assignments generated.")
                else:
                    print(
                        "Skipping bed assignments: Missing patient_ids, bed_ids, or visit_ids/visit_details_map."
                    )
            else:
                print("Skipping Bed Assignments insertion.")

            # Medical Records
            if INSERT_MEDICAL_RECORDS:
                if visit_ids and patient_ids:  # visit_details_map needs visit_ids
                    print("Inserting medical records...")
                    med_records_data_tuples = []
                    for v_id in visit_ids:
                        if v_id not in visit_details_map:
                            print(
                                f"Warning: Visit ID {v_id} not found in visit_details_map for medical record. Skipping."
                            )
                            continue
                        visit_data = visit_details_map[v_id]
                        record_type = random.choice(
                            [
                                "Consultation Note",
                                "Lab Report Summary",
                                "Imaging Report Finding",
                                "Progress Note",
                                "Discharge Summary",
                                "Referral Letter",
                            ]
                        )
                        details = {
                            "summary": faker.paragraph(
                                nb_sentences=random.randint(1, 3)
                            )
                        }
                        # ... (rest of details logic) ...
                        med_records_data_tuples.append(
                            (
                                v_id,
                                visit_data[0],  # patient_id
                                record_type,
                                json.dumps(details),
                                None,
                                visit_data[4]
                                + timedelta(minutes=random.randint(5, 60)),
                            )
                        )
                    if med_records_data_tuples:
                        med_record_ids = await insert_records(
                            conn,
                            "medical_records",
                            [
                                "visit_id",
                                "patient_id",
                                "record_type",
                                "record_details",
                                "document_path",
                                "created_at",
                            ],
                            med_records_data_tuples,
                            return_ids=True,
                        )
                        print(f"✓ Inserted {len(med_record_ids)} medical records")
                    else:
                        print("No medical records generated.")
                else:
                    print(
                        "Skipping medical records: Missing visit_ids/visit_details_map or patient_ids."
                    )
            else:
                print("Skipping Medical Records insertion.")

            # Treatments
            if INSERT_TREATMENTS:
                if visit_ids:  # visit_details_map needs visit_ids
                    print("Inserting treatments...")
                    # treatments_data initialized
                    # treatment_details_map initialized
                    for v_id in visit_ids:
                        if v_id not in visit_details_map:
                            print(
                                f"Warning: Visit ID {v_id} not found in visit_details_map for treatment. Skipping."
                            )
                            continue
                        if random.random() < 0.75:
                            num_treatments_for_visit = random.randint(1, 3)
                            if (
                                len(treatments_data) + num_treatments_for_visit
                                > NUM_TREATMENTS_TARGET
                            ):
                                num_treatments_for_visit = max(
                                    0, NUM_TREATMENTS_TARGET - len(treatments_data)
                                )
                            visit_datetime_start = visit_details_map[v_id][4]
                            for _ in range(num_treatments_for_visit):
                                treatments_data.append(  # Add to global
                                    (
                                        v_id,
                                        faker.word().capitalize()
                                        + " "
                                        + random.choice(
                                            [
                                                "Procedure",
                                                "Therapy",
                                                "Scan",
                                                "Test",
                                                "Intervention",
                                                "Counseling",
                                            ]
                                        ),
                                        faker.sentence(nb_words=random.randint(6, 12)),
                                        round(random.uniform(20, 3000), 2),
                                        visit_datetime_start
                                        + timedelta(hours=random.uniform(0.1, 3.0)),
                                    )
                                )
                            if len(treatments_data) >= NUM_TREATMENTS_TARGET:
                                break
                    if treatments_data:
                        treatment_ids = await insert_records(
                            conn,
                            "treatments",
                            [
                                "visit_id",
                                "treatment_name",
                                "description",
                                "cost",
                                "treatment_datetime",
                            ],
                            treatments_data,
                            return_ids=True,  # Use global
                        )
                        print(f"✓ Inserted {len(treatment_ids)} treatments")
                        treatment_details_map = {
                            treatment_ids[i]: treatments_data[i]
                            for i in range(len(treatment_ids))
                        }  # Populate global
                    else:
                        print("No treatments generated.")
                else:
                    print("Skipping treatments: Missing visit_ids/visit_details_map.")
            else:
                print("Skipping Treatments insertion.")

            # Prescriptions
            if INSERT_PRESCRIPTIONS:
                if visit_ids and doctor_ids and patient_ids:  # visit_details_map needed
                    print("Inserting prescriptions...")
                    # prescriptions_data_tuples initialized
                    for v_id in visit_ids:
                        if v_id not in visit_details_map:
                            print(
                                f"Warning: Visit ID {v_id} not found in visit_details_map for prescription. Skipping."
                            )
                            continue
                        if random.random() < 0.65:
                            visit_info = visit_details_map[v_id]
                            prescriptions_data_tuples.append(  # Add to global
                                (
                                    v_id,
                                    visit_info[1],
                                    visit_info[0],  # visit_id, doctor_id, patient_id
                                    (
                                        visit_info[4].date()
                                        if isinstance(visit_info[4], datetime)
                                        else datetime.now().date()
                                    ),
                                    (
                                        faker.sentence(nb_words=random.randint(3, 6))
                                        if random.random() < 0.2
                                        else None
                                    ),
                                )
                            )
                    if prescriptions_data_tuples:
                        prescription_ids = await insert_records(
                            conn,
                            "prescriptions",
                            [
                                "visit_id",
                                "doctor_id",
                                "patient_id",
                                "prescription_date",
                                "notes",
                            ],
                            prescriptions_data_tuples,
                            return_ids=True,  # Use global
                        )
                        print(f"✓ Inserted {len(prescription_ids)} prescriptions")

                        # Prescription Medications (nested under prescriptions)
                        if INSERT_PRESCRIPTION_MEDICATIONS:
                            if prescription_ids and medication_ids:
                                print("Inserting prescription medications...")
                                # prescription_med_data_collector initialized
                                # pm_details_map initialized
                                for pres_id in prescription_ids:
                                    num_meds_in_prescription = random.randint(1, 4)
                                    for _ in range(num_meds_in_prescription):
                                        prescription_med_data_collector.append(  # Add to global
                                            (
                                                pres_id,
                                                random.choice(medication_ids),
                                                f"{random.randint(1,3)} {random.choice(['tablet(s)', 'capsule(s)', 'ml', 'puff(s)', 'application(s)'])}",
                                                random.choice(
                                                    [
                                                        "Once daily (OD)",
                                                        "Twice daily (BD)",
                                                        "Thrice daily (TDS)",
                                                        "As needed (SOS/PRN)",
                                                        "Every 4-6 hours",
                                                    ]
                                                ),
                                                f"{random.randint(1,30)} {random.choice(['days', 'weeks', 'months', 'until review'])}",
                                                random.randint(1, 150),
                                            )
                                        )
                                if prescription_med_data_collector:
                                    prescription_medication_ids = await insert_records(
                                        conn,
                                        "prescription_medications",
                                        [
                                            "prescription_id",
                                            "medication_id",
                                            "dosage",
                                            "frequency",
                                            "duration",
                                            "quantity",
                                        ],
                                        prescription_med_data_collector,
                                        return_ids=True,  # Use global
                                    )
                                    print(
                                        f"✓ Inserted {len(prescription_medication_ids)} prescription medications items."
                                    )
                                    pm_details_map = {  # Populate global
                                        prescription_medication_ids[
                                            i
                                        ]: prescription_med_data_collector[i]
                                        for i in range(len(prescription_medication_ids))
                                    }
                                else:
                                    print("No prescription medication items generated.")
                            else:
                                print(
                                    "Skipping prescription medications: Missing prescription_ids or medication_ids."
                                )
                        else:
                            print("Skipping Prescription Medications insertion.")
                    else:
                        print("No prescriptions generated.")
                else:
                    print(
                        "Skipping prescriptions: Missing visit_ids/doctor_ids/patient_ids or visit_details_map."
                    )
            else:
                print(
                    "Skipping Prescriptions (and Prescription Medications) insertion."
                )

            # Bills
            if INSERT_BILLS:
                if patient_ids:
                    print("Inserting bills...")
                    # bills_data initialized
                    # bill_info_map_for_items initialized
                    visits_to_bill_ids_sample = (
                        random.sample(
                            visit_ids, min(len(visit_ids), int(NUM_BILLS_TARGET * 0.9))
                        )
                        if visit_ids
                        else []
                    )

                    for v_id in visits_to_bill_ids_sample:
                        if v_id not in visit_details_map:
                            print(
                                f"Warning: Visit ID {v_id} not found in visit_details_map for bill creation. Skipping this bill."
                            )
                            continue
                        visit_info = visit_details_map[v_id]
                        bill_date = (
                            visit_info[4].date()
                            if isinstance(visit_info[4], datetime)
                            else datetime.now().date()
                        )
                        due_date = bill_date + timedelta(days=random.randint(10, 45))
                        status = random.choice(
                            ["pending", "paid", "partially_paid", "overdue", "draft"]
                        )
                        bills_data.append(  # Add to global
                            (
                                visit_info[0],
                                v_id,
                                bill_date,
                                due_date,
                                0.0,
                                0.0,
                                status,  # patient_id, visit_id, total, paid
                                (
                                    random.choice(
                                        [
                                            "Credit Card",
                                            "Cash",
                                            "Insurance Claim",
                                            "Bank Transfer",
                                        ]
                                    )
                                    if status in ["paid", "partially_paid"]
                                    else None
                                ),
                                (
                                    faker.unique.iban()
                                    if status in ["paid", "partially_paid"]
                                    else None
                                ),
                            )
                        )

                    num_other_bills = NUM_BILLS_TARGET - len(bills_data)
                    for _ in range(max(0, num_other_bills)):
                        p_id = random.choice(patient_ids)
                        bill_date = random_date("2021-01-01", "today")
                        due_date = bill_date + timedelta(days=random.randint(10, 45))
                        status = random.choice(
                            [
                                "pending",
                                "paid",
                                "partially_paid",
                                "overdue",
                                "draft",
                                "cancelled",
                            ]
                        )
                        bills_data.append(  # Add to global
                            (
                                p_id,
                                None,
                                bill_date,
                                due_date,
                                0.0,
                                0.0,
                                status,
                                (
                                    random.choice(
                                        [
                                            "Credit Card",
                                            "Cash",
                                            "Insurance Claim",
                                            "Bank Transfer",
                                        ]
                                    )
                                    if status in ["paid", "partially_paid"]
                                    else None
                                ),
                                (
                                    faker.unique.iban()
                                    if status in ["paid", "partially_paid"]
                                    else None
                                ),
                            )
                        )
                    faker.unique.clear()

                    if bills_data:
                        bill_ids_generated = await insert_records(
                            conn,
                            "bills",
                            [
                                "patient_id",
                                "visit_id",
                                "bill_date",
                                "due_date",
                                "total_amount",
                                "paid_amount",
                                "status",
                                "payment_method",
                                "transaction_id",
                            ],
                            bills_data,
                            return_ids=True,  # Use global
                        )
                        print(
                            f"✓ Inserted {len(bill_ids_generated)} bills (totals to be updated)."
                        )
                        bill_info_map_for_items = {
                            bill_ids_generated[i]: bills_data[i]
                            for i in range(len(bill_ids_generated))
                        }  # Populate global

                        # Bill Items (nested under bills)
                        if INSERT_BILL_ITEMS:
                            print("Inserting bill items and updating bill totals...")
                            bill_items_data_tuples = []
                            billed_treatments = set()
                            billed_presc_meds = set()

                            for b_id in bill_ids_generated:
                                bill_meta_info = bill_info_map_for_items[b_id]
                                visit_id_for_bill = bill_meta_info[1]
                                current_bill_total = 0.0

                                if (
                                    visit_id_for_bill
                                    and visit_id_for_bill in visit_details_map
                                ):  # Items related to a visit
                                    consult_fee = round(random.uniform(30, 350), 2)
                                    bill_items_data_tuples.append(
                                        (
                                            b_id,
                                            "Doctor Consultation / Visit Fee",
                                            "consultation",
                                            1,
                                            consult_fee,
                                            consult_fee,
                                            None,
                                            None,
                                        )
                                    )
                                    current_bill_total += consult_fee

                                    for (
                                        t_id,
                                        t_data_tuple,
                                    ) in treatment_details_map.items():
                                        if (
                                            t_data_tuple[0] == visit_id_for_bill
                                            and t_id not in billed_treatments
                                        ):
                                            cost = t_data_tuple[3]
                                            bill_items_data_tuples.append(
                                                (
                                                    b_id,
                                                    f"Treatment: {t_data_tuple[1]}",
                                                    "procedure",
                                                    1,
                                                    cost,
                                                    cost,
                                                    t_id,
                                                    None,
                                                )
                                            )
                                            current_bill_total += cost
                                            billed_treatments.add(t_id)

                                    prescs_for_this_visit = [
                                        pid
                                        for pid, pdata_tuple in zip(
                                            prescription_ids, prescriptions_data_tuples
                                        )
                                        if pdata_tuple[0] == visit_id_for_bill
                                    ]
                                    for presc_id_for_bill in prescs_for_this_visit:
                                        for (
                                            pm_id,
                                            pm_data_tuple,
                                        ) in pm_details_map.items():
                                            if (
                                                pm_data_tuple[0] == presc_id_for_bill
                                                and pm_id not in billed_presc_meds
                                            ):
                                                med_id = pm_data_tuple[1]
                                                if (
                                                    med_id in medication_ids
                                                    and medications_data
                                                ):  # Ensure med_id and medications_data are valid
                                                    try:
                                                        med_info_idx = (
                                                            medication_ids.index(med_id)
                                                        )
                                                        if med_info_idx < len(
                                                            medications_data
                                                        ):
                                                            med_price = (
                                                                medications_data[
                                                                    med_info_idx
                                                                ][5]
                                                            )
                                                            quantity = pm_data_tuple[5]
                                                            item_total = round(
                                                                med_price * quantity, 2
                                                            )
                                                            bill_items_data_tuples.append(
                                                                (
                                                                    b_id,
                                                                    f"Medication: {medications_data[med_info_idx][0]}",
                                                                    "medication",
                                                                    quantity,
                                                                    med_price,
                                                                    item_total,
                                                                    None,
                                                                    pm_id,
                                                                )
                                                            )
                                                            current_bill_total += (
                                                                item_total
                                                            )
                                                            billed_presc_meds.add(pm_id)
                                                        else:
                                                            print(
                                                                f"Warning: med_info_idx out of bounds for medications_data. Med ID: {med_id}"
                                                            )
                                                    except ValueError:
                                                        print(
                                                            f"Warning: Medication ID {med_id} not found in medication_ids list for bill item."
                                                        )
                                                else:
                                                    print(
                                                        f"Warning: Medication ID {med_id} or medications_data not available for bill item."
                                                    )
                                else:  # Bill not tied to a specific visit
                                    num_misc_items = random.randint(1, 3)
                                    for _ in range(num_misc_items):
                                        item_type = random.choice(
                                            ["service", "test", "other"]
                                        )
                                        desc = f"{faker.bs().split(' ')[0]} {item_type.capitalize()}"
                                        qty = random.randint(1, 2)
                                        u_price = round(random.uniform(10, 200), 2)
                                        bill_items_data_tuples.append(
                                            (
                                                b_id,
                                                desc,
                                                item_type,
                                                qty,
                                                u_price,
                                                round(qty * u_price, 2),
                                                None,
                                                None,
                                            )
                                        )
                                        current_bill_total += round(qty * u_price, 2)

                                if current_bill_total > 0:
                                    final_paid_amount = 0
                                    bill_status = bill_meta_info[6]
                                    if bill_status == "paid":
                                        final_paid_amount = current_bill_total
                                    elif bill_status == "partially_paid":
                                        final_paid_amount = round(
                                            current_bill_total
                                            * random.uniform(0.1, 0.8),
                                            2,
                                        )
                                    await conn.execute(
                                        "UPDATE bills SET total_amount = $1, paid_amount = $2 WHERE id = $3",
                                        current_bill_total,
                                        final_paid_amount,
                                        b_id,
                                    )

                            if bill_items_data_tuples:
                                bill_item_ids = await insert_records(
                                    conn,
                                    "bill_items",
                                    [
                                        "bill_id",
                                        "item_description",
                                        "item_type",
                                        "quantity",
                                        "unit_price",
                                        "total_price",
                                        "treatment_id",
                                        "prescription_medication_id",
                                    ],
                                    bill_items_data_tuples,
                                    return_ids=True,
                                )
                                print(
                                    f"✓ Inserted {len(bill_item_ids)} bill items and updated bill totals."
                                )
                            else:
                                print("No bill items were generated.")
                        else:
                            print("Skipping Bill Items insertion.")
                    else:
                        print(
                            "No bills generated (totals cannot be updated, bill items skipped)."
                        )
                else:
                    print("Skipping bills (and bill items): Missing patient_ids.")
            else:
                print("Skipping Bills (and Bill Items) insertion.")

            print("\n✅ Data population process completed based on flags!")

    except Exception as e:
        print(f"\n❌ An error occurred in main: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if pool:
            await pool.close()
            print("Connection pool closed.")


if __name__ == "__main__":
    asyncio.run(main())

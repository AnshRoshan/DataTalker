-- sql_files/create.sql

-- Drop tables in reverse order of creation due to dependencies
DROP TABLE IF EXISTS bill_items CASCADE;
DROP TABLE IF EXISTS bills CASCADE;
DROP TABLE IF EXISTS prescription_medications CASCADE;
DROP TABLE IF EXISTS prescriptions CASCADE;
DROP TABLE IF EXISTS treatments CASCADE;
DROP TABLE IF EXISTS medical_records CASCADE;
DROP TABLE IF EXISTS bed_assignments CASCADE;
DROP TABLE IF EXISTS visits CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS medications CASCADE;
DROP TABLE IF EXISTS insurance_policies CASCADE;
DROP TABLE IF EXISTS insurance_providers CASCADE;
DROP TABLE IF EXISTS beds CASCADE;
DROP TABLE IF EXISTS wards CASCADE;
ALTER TABLE IF EXISTS departments DROP CONSTRAINT IF EXISTS fk_head_doctor; -- Drop constraint before dropping doctors
DROP TABLE IF EXISTS doctors CASCADE;
DROP TABLE IF EXISTS staff CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS hospitals CASCADE;

-- Hospitals
CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    address TEXT,
    phone_number VARCHAR(30),
    email VARCHAR(100) UNIQUE,
    website VARCHAR(100),
    established_date DATE
);

-- Departments
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    description TEXT,
    head_doctor_id INTEGER -- Will be constrained later to doctors(id)
);

-- Staff (General staff, Nurses, Admin, Technicians etc.)
CREATE TABLE staff (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(100) NOT NULL, 
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    salary NUMERIC(10, 2) CHECK (salary > 0),
    hire_date DATE NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(100) UNIQUE,
    address TEXT
);

-- Doctors (Specialized medical practitioners)
CREATE TABLE doctors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    specialization VARCHAR(100) NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    phone VARCHAR(50),
    email VARCHAR(100) UNIQUE,
    license_number VARCHAR(50) UNIQUE,
    years_of_experience INTEGER CHECK (years_of_experience >= 0)
);

-- Add FK for department's head_doctor_id now that doctors table exists
ALTER TABLE departments ADD CONSTRAINT fk_head_doctor FOREIGN KEY (head_doctor_id) REFERENCES doctors(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

-- Patients
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(20) CHECK (gender IN ('Male', 'Female', 'Other', 'Prefer not to say')),
    phone VARCHAR(50),
    email VARCHAR(100) UNIQUE,
    address TEXT,
    blood_type VARCHAR(5), 
    allergies TEXT 
);

-- Insurance Providers
CREATE TABLE insurance_providers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    phone_number VARCHAR(50),
    address TEXT,
    email VARCHAR(100)
);

-- Insurance Policies
CREATE TABLE insurance_policies (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    provider_id INTEGER NOT NULL REFERENCES insurance_providers(id) ON DELETE RESTRICT,
    policy_number VARCHAR(50) NOT NULL,
    coverage_details JSONB, 
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    UNIQUE(provider_id, policy_number) -- Policy number unique per provider
);

-- Wards
CREATE TABLE wards (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL, 
    capacity INTEGER NOT NULL CHECK (capacity > 0)
);

-- Beds
CREATE TABLE beds (
    id SERIAL PRIMARY KEY,
    bed_number VARCHAR(20) NOT NULL,
    ward_id INTEGER NOT NULL REFERENCES wards(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'available' CHECK (status IN ('available', 'occupied', 'maintenance', 'reserved')),
    bed_type VARCHAR(50) DEFAULT 'Standard',
    UNIQUE(ward_id, bed_number)
);

-- Appointments
CREATE TABLE appointments (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    department_id INTEGER REFERENCES departments(id) ON DELETE RESTRICT, 
    appointment_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no-show', 'rescheduled')),
    reason TEXT,
    notes TEXT 
);

-- Visits (Actual encounters)
CREATE TABLE visits (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT, 
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE RESTRICT, 
    appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL, 
    visit_datetime_start TIMESTAMP WITH TIME ZONE NOT NULL,
    visit_datetime_end TIMESTAMP WITH TIME ZONE,
    visit_type VARCHAR(50) CHECK (visit_type IN ('OPD', 'Emergency', 'Follow-up', 'In-patient Consult', 'Routine Checkup')),
    symptoms TEXT,
    diagnosis TEXT,
    notes TEXT,
    CONSTRAINT check_visit_end_after_start CHECK (visit_datetime_end IS NULL OR visit_datetime_end >= visit_datetime_start)
);

-- Bed Assignments (Tracking patient stays in beds)
CREATE TABLE bed_assignments (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    bed_id INTEGER NOT NULL REFERENCES beds(id) ON DELETE RESTRICT,
    visit_id INTEGER REFERENCES visits(id) ON DELETE SET NULL, 
    admission_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    discharge_datetime TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    CONSTRAINT check_discharge_after_admission CHECK (discharge_datetime IS NULL OR discharge_datetime > admission_datetime)
);

-- Medical Records (Detailed records, test results, etc., linked to visits)
CREATE TABLE medical_records (
    id SERIAL PRIMARY KEY,
    visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE, 
    record_type VARCHAR(100) NOT NULL, 
    record_details JSONB, 
    document_path VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Medications
CREATE TABLE medications (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    manufacturer VARCHAR(100),
    dosage_form VARCHAR(50), 
    strength VARCHAR(50), 
    unit_price NUMERIC(10, 2) CHECK (unit_price >= 0)
);

-- Treatments (Procedures, therapies, etc., performed during a visit)
CREATE TABLE treatments (
    id SERIAL PRIMARY KEY,
    visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    treatment_name VARCHAR(150) NOT NULL,
    description TEXT,
    cost NUMERIC(10, 2) NOT NULL CHECK (cost >= 0),
    treatment_datetime TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Prescriptions
CREATE TABLE prescriptions (
    id SERIAL PRIMARY KEY,
    visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT, 
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE, 
    prescription_date DATE NOT NULL DEFAULT CURRENT_DATE,
    notes TEXT
);

-- Prescription Medications (Junction table for Prescriptions and Medications)
CREATE TABLE prescription_medications (
    id SERIAL PRIMARY KEY,
    prescription_id INTEGER NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    medication_id INTEGER NOT NULL REFERENCES medications(id) ON DELETE RESTRICT,
    dosage VARCHAR(100), 
    frequency VARCHAR(100), 
    duration VARCHAR(100), 
    quantity INTEGER CHECK (quantity > 0),
    notes TEXT
);

-- Bills
CREATE TABLE bills (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    visit_id INTEGER REFERENCES visits(id) ON DELETE SET NULL, 
    bill_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE,
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    paid_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL CHECK (status IN ('draft', 'pending', 'paid', 'partially_paid', 'overdue', 'cancelled', 'waived')),
    payment_method VARCHAR(50),
    transaction_id VARCHAR(100),
    CONSTRAINT check_paid_amount CHECK (paid_amount <= total_amount),
    CONSTRAINT check_due_date CHECK (due_date IS NULL OR due_date >= bill_date)
);

-- Bill Items (Breakdown of a bill)
CREATE TABLE bill_items (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    item_description VARCHAR(255) NOT NULL,
    item_type VARCHAR(50) NOT NULL CHECK (item_type IN ('service', 'medication', 'procedure', 'consultation', 'test', 'room_charge', 'other')), 
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    -- total_price NUMERIC(10, 2) GENERATED ALWAYS AS (quantity * unit_price) STORED, -- PG 12+
    total_price NUMERIC(10,2) NOT NULL, -- For compatibility, calculate in app or use trigger
    treatment_id INTEGER REFERENCES treatments(id) ON DELETE SET NULL, 
    prescription_medication_id INTEGER REFERENCES prescription_medications(id) ON DELETE SET NULL 
);

-- Indexes for performance
CREATE INDEX idx_doctors_department_id ON doctors(department_id);
CREATE INDEX idx_patients_name ON patients(name);
CREATE INDEX idx_appointments_patient_id ON appointments(patient_id);
CREATE INDEX idx_appointments_doctor_id ON appointments(doctor_id);
CREATE INDEX idx_appointments_datetime ON appointments(appointment_datetime);
CREATE INDEX idx_visits_patient_id ON visits(patient_id);
CREATE INDEX idx_visits_doctor_id ON visits(doctor_id);
CREATE INDEX idx_visits_datetime_start ON visits(visit_datetime_start);
CREATE INDEX idx_prescriptions_visit_id ON prescriptions(visit_id);
CREATE INDEX idx_bills_patient_id ON bills(patient_id);
CREATE INDEX idx_bills_status ON bills(status);
CREATE INDEX idx_staff_hospital_id ON staff(hospital_id);
CREATE INDEX idx_staff_department_id ON staff(department_id);
CREATE INDEX idx_insurance_policies_patient_id ON insurance_policies(patient_id);
CREATE INDEX idx_bed_assignments_patient_id ON bed_assignments(patient_id);
CREATE INDEX idx_bed_assignments_bed_id ON bed_assignments(bed_id);
CREATE INDEX idx_medical_records_visit_id ON medical_records(visit_id);

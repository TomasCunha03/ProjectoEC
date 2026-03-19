-- 1. Main Disease table
CREATE TABLE IF NOT EXISTS diseases (
    disease_id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT
);

-- 2. Symptoms and their severity weights
CREATE TABLE IF NOT EXISTS symptoms (
    symptom_id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    severity_weight INT
);

-- 3. Mapping Disease to Symptoms (Many-to-Many)
CREATE TABLE IF NOT EXISTS disease_symptoms (
    disease_id INT REFERENCES diseases(disease_id),
    symptom_id INT REFERENCES symptoms(symptom_id),
    PRIMARY KEY (disease_id, symptom_id)
);

-- 4. Precautions for each disease
CREATE TABLE IF NOT EXISTS disease_precautions (
    precaution_id SERIAL PRIMARY KEY,
    disease_id INT REFERENCES diseases(disease_id),
    precaution TEXT NOT NULL
);

-- Table for Global Health Statistics
CREATE TABLE IF NOT EXISTS global_health_stats (
    stat_id SERIAL PRIMARY KEY,
    country VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    disease_name VARCHAR(255) NOT NULL,
    disease_category VARCHAR(100),
    prevalence_rate DECIMAL(5,2),
    incidence_rate DECIMAL(5,2),
    mortality_rate DECIMAL(5,2),
    age_group VARCHAR(50),
    gender VARCHAR(20),
    population_affected INT,
    healthcare_access_pct DECIMAL(5,2),
    doctors_per_1000 DECIMAL(5,2),
    hospital_beds_per_1000 DECIMAL(5,2),
    treatment_type VARCHAR(100),
    average_treatment_cost_usd DECIMAL(12,2),
    availability_vaccines_treatment VARCHAR(10),
    recovery_rate DECIMAL(5,2),
    dalys INT,
    improvement_5yr_pct DECIMAL(5,2),
    per_capita_income_usd DECIMAL(12,2),
    education_index DECIMAL(4,3),
    urbanization_rate_pct DECIMAL(5,2),
    -- Unique constraint to avoid duplicates if the script is run multiple times
    UNIQUE(country, year, disease_name, age_group, gender)
);

CREATE TABLE IF NOT EXISTS chronic_disease_indicators (
    indicator_id SERIAL PRIMARY KEY,
    year_start INT,
    year_end INT,
    location_abbr VARCHAR(10),
    location_desc VARCHAR(255),
    datasource VARCHAR(100),
    topic VARCHAR(255),
    question TEXT,
    response TEXT,
    data_value_unit VARCHAR(50),
    data_value_type VARCHAR(100),
    data_value DECIMAL(18,2),
    low_confidence_limit DECIMAL(18,2),
    high_confidence_limit DECIMAL(18,2),
    stratification_category_1 VARCHAR(100),
    stratification_1 VARCHAR(100),
    geolocation VARCHAR(255),
    location_id VARCHAR(10),
    topic_id VARCHAR(50),
    question_id VARCHAR(50),
    stratification_id_1 VARCHAR(50)
);


CREATE TABLE IF NOT EXISTS brfss_responses (
    brfss_id SERIAL PRIMARY KEY,
    state_code INT,

    -- Diagnoses and health conditions (the "Diagnosis" block)
    diagnosed_diabetes INT,      -- DIABETE4: Diabetes
    diagnosed_asthma INT,        -- ASTHMA3: Asthma (ever)
    asthma_now INT,              -- ASTHNOW: Asthma currently
    diagnosed_stroke INT,        -- CVDSTRK3: Stroke
    diagnosed_heart_attack INT,  -- CVDINFR4: Myocardial infarction (heart attack)
    diagnosed_heart_dis INT,     -- CVDCRHD4: Coronary heart disease
    diagnosed_copd INT,          -- CHCCOPD3: COPD, emphysema, or chronic bronchitis
    diagnosed_depressive INT,    -- ADDEPEV3: Depressive disorder
    diagnosed_kidney_dis INT,    -- CHCKDNY2: Kidney disease (excluding stones/infection)
    diagnosed_arthritis INT,     -- HAVARTH4: Arthritis, gout, lupus, or rheumatism
    diagnosed_skin_cancer INT,   -- CHCSCNC1: Skin cancer
    diagnosed_other_cancer INT,  -- CHCOCNC1: Other types of cancer
    
    -- Prevention and risk indicators (the "Lifestyle" block)
    high_blood_pressure INT,     -- BPHIGH6: High blood pressure
    high_cholesterol INT,        -- TOLDHI3: High cholesterol
    smoke_100 INT,               -- SMOKE100: Has smoked 100 cigarettes
    alcohol_binge INT,           -- _RFBING6: Binge drinking indicator
    exercise_any INT,            -- EXERANY2: Physical activity
    
    -- Physical and mental health data
    general_health INT,          -- GENHLTH: Self-rated health
    physical_health_days INT,    -- PHYSHLTH: Poor physical health days
    mental_health_days INT,      -- MENTHLTH: Poor mental health days
    
    -- Biometric data
    weight_kg DECIMAL(6,2),      -- WTKG3
    height_cm INT,               -- HTM4
    bmi DECIMAL(6,2),            -- _BMI5
    
    -- Unique identifier
    sequence_no BIGINT UNIQUE
);



-- Dataset WUENIC


CREATE TABLE IF NOT EXISTS country_dim (
    id SERIAL PRIMARY KEY,
    iso_code VARCHAR(3) UNIQUE NOT NULL,
    country_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vaccine_dim (
    id SERIAL PRIMARY KEY,
    vaccine_code TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS immunization_fact (
    id BIGSERIAL PRIMARY KEY,
    country_id INT REFERENCES country_dim(id),
    vaccine_id INT REFERENCES vaccine_dim(id),
    year INT NOT NULL,
    wuenic_coverage NUMERIC(5,2),
    administrative_coverage NUMERIC(5,2),
    children_vaccinated BIGINT,
    children_target BIGINT,
    births_unpd BIGINT,
    surviving_infants BIGINT,
    calculated_coverage NUMERIC(5,2),
    anomaly_flag BOOLEAN DEFAULT FALSE,
    UNIQUE(country_id, vaccine_id, year)
);

CREATE TABLE IF NOT EXISTS drugs_side_effects (
    id SERIAL PRIMARY KEY,
    drug_name TEXT,
    medical_condition TEXT,
    side_effects TEXT,
    generic_name TEXT,
    drug_classes TEXT,
    brand_names TEXT,
    activity TEXT,
    rx_otc TEXT,
    pregnancy_category TEXT,
    csa TEXT,
    alcohol TEXT,
    related_drugs TEXT,
    medical_condition_description TEXT,
    rating NUMERIC,
    no_of_reviews INTEGER,
    drug_link TEXT,
    medical_condition_url TEXT,
    UNIQUE (drug_name, medical_condition)
);

-- Database and User Setup for Bushfire Plan Application
-- For DBeaver: Run Step 1 connected to 'postgres' database, then Step 2 connected to 'bushfire_plans' database

-- STEP 1: Run these commands connected to the 'postgres' database
-- Create database
CREATE DATABASE bushfire_plans;

-- Create user
CREATE USER bfp_agent WITH PASSWORD 'bushfire_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE bushfire_plans TO bfp_agent;

-- STEP 2: Create new connection to 'bushfire_plans' database in DBeaver and run the commands below
-- Create project schema
CREATE SCHEMA bushfire_plans;

-- Grant schema privileges
GRANT ALL ON SCHEMA bushfire_plans TO bfp_agent;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA bushfire_plans TO bfp_agent;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA bushfire_plans TO bfp_agent;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA bushfire_plans GRANT ALL ON TABLES TO bfp_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA bushfire_plans GRANT ALL ON SEQUENCES TO bfp_agent;

-- Set default schema for user
ALTER USER bfp_agent SET search_path = bushfire_plans;

-- Note: LangGraph will automatically create required tables when the application starts
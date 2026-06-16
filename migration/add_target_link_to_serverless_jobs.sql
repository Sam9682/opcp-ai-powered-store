-- Migration: Add target_link column to serverless_jobs table
-- Stores the selected opcp-serverless-brik endpoint URL to execute the job on
-- Date: 2026-06-16

ALTER TABLE serverless_jobs
ADD COLUMN IF NOT EXISTS target_link TEXT;

COMMENT ON COLUMN serverless_jobs.target_link IS 'The opcp-serverless-brik endpoint URL selected for job execution';

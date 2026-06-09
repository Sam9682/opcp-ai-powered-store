# Implementation Plan: MIG Shared GPU

## Overview

This plan implements NVIDIA Multi-Instance GPU (MIG) support for the SwAutoMorph platform. The implementation progresses through database schema, platform init script extension, Flask API blueprint with SSH-based GPU management, and a web UI for administrators. Each task builds on the previous, ending with full integration.

## Tasks

- [x] 1. Database schema and migration
  - [x] 1.1 Create the `migration/add_mig_gpu.sql` migration file
    - Add `shared_gpu_enabled BOOLEAN DEFAULT FALSE` column to `servers` table using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
    - Create `mig_profiles` table with columns: id (SERIAL PK), server_id (FK to servers ON DELETE CASCADE), profile_name (VARCHAR(64)), profile_id (VARCHAR(128)), gpu_memory_gb (INTEGER CHECK 1-80), created_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP), UNIQUE(server_id, profile_name)
    - Create `mig_instances` table with columns: id (SERIAL PK), server_id (FK to servers ON DELETE CASCADE), instance_uuid (VARCHAR(36)), profile_name (VARCHAR(50)), gpu_memory_mb (INTEGER CHECK 1-81920), created_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP), UNIQUE(server_id, instance_uuid)
    - Add indexes: `idx_mig_profiles_server_id` on mig_profiles(server_id), `idx_mig_instances_server_id` on mig_instances(server_id)
    - _Requirements: 3.1, 4.1, 4.3, 4.4, 5.1, 5.4, 5.5_

  - [x] 1.2 Register the migration in `src/database_postgres.py` `init_db()` function
    - Add a migration block following the existing `add_serverless_jobs.sql` pattern
    - Read and execute `migration/add_mig_gpu.sql` with rollback on error
    - _Requirements: 3.1, 4.1, 5.1_

- [x] 2. Platform initialization script extension
  - [x] 2.1 Add NVIDIA driver and MIG setup section to `init_pltf.sh`
    - Insert after the Docker installation block
    - Install `nvidia-driver-550` and `nvidia-utils-550` with `sudo apt install -y`
    - On success: enable MIG mode with `sudo nvidia-smi -mig 1`
    - On MIG success: install `nvidia-container-toolkit`
    - On toolkit success: verify Docker GPU access with `timeout 30 docker run --rm --gpus '"device=0"' nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi`
    - Use existing `print_step`, `print_success`, `print_warning` helpers
    - On any failure: log warning and continue (never abort the script)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3_

- [x] 3. GPU routes blueprint — helper functions and structure
  - [x] 3.1 Create `src/routes/gpu_routes.py` with blueprint skeleton and auth helpers
    - Create `gpu_bp` Blueprint with prefix `/api/servers/<int:server_id>/gpu`
    - Implement `require_admin()` function using `session.get('user_id')` and admin check (same pattern as orchestrator_routes.py)
    - Implement `get_server_ip(server_id)` helper that queries the `servers` table
    - Implement `ssh_execute(server_ip, command, timeout=30)` helper using `subprocess.run()` with SSH flags (`-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null`)
    - Set up logging following orchestrator_routes.py pattern
    - _Requirements: 11.6, 11.7, 11.8_

  - [x] 3.2 Implement `parse_mig_profiles(output)` parser function
    - Parse `nvidia-smi mig -lgip` output into a list of dicts with keys: `profile_id` (int), `name` (str), `memory_mib` (int)
    - Handle edge cases: empty output, malformed lines, extra whitespace
    - _Requirements: 6.2_

  - [x] 3.3 Implement `parse_mig_instances(output)` parser function
    - Parse `nvidia-smi -L` output to extract MIG instance entries
    - Extract UUID (pattern `MIG-<uuid>`) and associated profile name for each MIG device line
    - Handle edge cases: no MIG devices, multiple GPUs, mixed output
    - _Requirements: 7.4_

  - [x] 3.4 Implement `validate_profile_ids(profile_ids)` validation function
    - Reject empty lists (length 0)
    - Reject lists with more than 7 entries
    - Return error message on rejection, None on success
    - _Requirements: 7.2, 11.9_

  - [x] 3.5 Implement `build_mig_create_command(profile_ids)` command builder
    - Construct `sudo nvidia-smi mig -cgi <comma_separated_ids> -C`
    - Preserve input order of profile IDs
    - _Requirements: 7.1_

  - [ ]* 3.6 Write property tests for parser and validation functions
    - **Property 1: MIG profile list ordering** — Generate random profile lists, verify DB query returns sorted by name
    - **Validates: Requirements 4.2**

  - [ ]* 3.7 Write property test for nvidia-smi profile output parsing
    - **Property 2: nvidia-smi profile output parsing** — Generate random valid nvidia-smi profile outputs, verify parser extracts correct count and fields
    - **Validates: Requirements 6.2**

  - [ ]* 3.8 Write property test for MIG command construction
    - **Property 3: MIG instance creation command construction** — Generate random lists of 1-7 profile IDs, verify command contains all IDs comma-separated in order
    - **Validates: Requirements 7.1**

  - [ ]* 3.9 Write property test for profile ID list validation
    - **Property 4: Profile ID list validation rejects invalid lengths** — Generate lists of length 0 or >7, verify validation always rejects
    - **Validates: Requirements 7.2, 11.9**

  - [ ]* 3.10 Write property test for nvidia-smi instance output parsing
    - **Property 5: nvidia-smi instance output parsing** — Generate random nvidia-smi -L outputs with MIG UUIDs, verify parser extracts all entries
    - **Validates: Requirements 7.4**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. GPU routes blueprint — API endpoints
  - [x] 5.1 Implement `PUT /api/servers/<server_id>/gpu/enabled` endpoint
    - Validate request body contains boolean `enabled` field
    - Check server exists (return 404 if not)
    - Update `shared_gpu_enabled` column in `servers` table
    - Return updated server state as JSON
    - _Requirements: 3.2, 3.3, 3.4, 11.5_

  - [x] 5.2 Implement `GET /api/servers/<server_id>/gpu/profiles` endpoint
    - Validate server exists (return 404 if not)
    - SSH to server and execute `nvidia-smi mig -lgip` with 30s timeout
    - Parse output using `parse_mig_profiles()`
    - Return structured list of profiles
    - Handle MIG not available and server unreachable errors
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 11.1_

  - [x] 5.3 Implement `GET /api/servers/<server_id>/gpu/instances` endpoint
    - Validate server exists (return 404 if not)
    - Query `mig_instances` table for the given server_id
    - Return instances ordered by creation timestamp
    - _Requirements: 5.1, 11.2_

  - [x] 5.4 Implement `POST /api/servers/<server_id>/gpu/instances` endpoint
    - Validate server exists and `shared_gpu_enabled` is true
    - Validate `profile_ids` list (1-7 entries, non-empty)
    - Build and execute `sudo nvidia-smi mig -cgi <ids> -C` via SSH with 30s timeout
    - On success, execute `nvidia-smi -L` to get instance details
    - Parse instance UUIDs and persist to `mig_instances` table
    - Handle partial failures (creation succeeds but -L fails)
    - Return created instances or appropriate error
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 11.3, 11.9_

  - [x] 5.5 Implement `DELETE /api/servers/<server_id>/gpu/instances` endpoint
    - Validate server exists (return 404 if not)
    - Check that MIG instances exist for the server (return 400 if none)
    - Execute `sudo nvidia-smi mig -dci` then `sudo nvidia-smi mig -dgi` via SSH
    - Only remove DB records if both commands succeed
    - Handle partial failure (first succeeds, second fails)
    - Return count of destroyed instances
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 11.4_

  - [ ]* 5.6 Write unit tests for GPU API endpoints
    - Test auth guards (401 for unauthenticated, 403 for non-admin)
    - Test 404 for non-existent server_id
    - Test validation errors (empty profile_ids, >7 profiles, missing enabled field)
    - Test shared_gpu_enabled=false rejection on create
    - Mock SSH calls for success and failure scenarios
    - _Requirements: 11.6, 11.7, 11.8, 11.9_

- [x] 6. Register GPU blueprint in the application
  - [x] 6.1 Register `gpu_bp` in `src/routes/__init__.py` or the app factory
    - Import `gpu_bp` from `src.routes.gpu_routes`
    - Register with the Flask app following existing blueprint registration pattern
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Web UI — Shared GPU page
  - [x] 8.1 Add route for shared GPU page in `src/routes/main_routes.py`
    - Add `GET /servers/<int:server_id>/gpu` route
    - Enforce admin authentication
    - Render `shared_gpu.html` template with server_id context
    - _Requirements: 9.2, 9.3, 9.4_

  - [x] 8.2 Create `templates/shared_gpu.html` template
    - Extend `base.html`
    - Display server identification header with server name/IP
    - Add toggle switch for shared GPU enabled/disabled (calls PUT /enabled endpoint)
    - Add "Available MIG Profiles" table (fetched from GET /profiles endpoint)
    - Add profile selection checkboxes and "Create Instances" button (calls POST /instances)
    - Add "Active MIG Instances" table showing UUID, profile name, memory, timestamp (fetched from GET /instances)
    - Add "Destroy All Instances" button (calls DELETE /instances)
    - Add status/error message display area
    - Use JavaScript fetch() for API calls with proper error handling
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.11_

  - [x] 8.3 Add "Shared-GPU" button to the Server Management page
    - Add button in the actions column of the server grid (in the dashboard template)
    - Button navigates to `/servers/<server_id>/gpu`
    - Only render for admin users
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 9. Toggle enable/disable with MIG mode command
  - [x] 9.1 Extend the PUT `/enabled` endpoint to execute MIG mode command on enable
    - When enabling (`enabled: true`): execute `sudo nvidia-smi -mig 1` on the server via SSH
    - If MIG command fails: revert `shared_gpu_enabled` to `false` in DB, return error
    - When disabling (`enabled: false`): only update the DB flag (no CLI command needed)
    - _Requirements: 10.7, 10.8, 10.9_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The SSH execution pattern matches `orchestrator_routes.py` (subprocess.run with StrictHostKeyChecking=no)
- All GPU endpoints are admin-only, following the session-based auth pattern
- The migration file uses `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` for idempotency

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5"] },
    { "id": 4, "tasks": ["3.6", "3.7", "3.8", "3.9", "3.10"] },
    { "id": 5, "tasks": ["5.1", "5.2", "5.3", "6.1"] },
    { "id": 6, "tasks": ["5.4", "5.5"] },
    { "id": 7, "tasks": ["5.6", "8.1"] },
    { "id": 8, "tasks": ["8.2", "8.3", "9.1"] }
  ]
}
```

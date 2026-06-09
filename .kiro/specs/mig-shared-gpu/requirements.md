# Requirements Document

## Introduction

This feature adds NVIDIA Multi-Instance GPU (MIG) shared GPU support to the SwAutoMorph platform. MIG allows a single physical GPU (such as NVIDIA H100) to be partitioned into multiple isolated GPU instances, each with dedicated compute, memory, and bandwidth resources. The platform will support installing NVIDIA drivers during platform initialization, storing MIG configuration in the database, managing MIG instances via CLI commands, and providing a web interface for administrators to enable and configure shared GPU on a per-server basis.

## Glossary

- **Platform_Init_Script**: The `init_pltf.sh` shell script that initializes a new server with required software and configuration
- **MIG**: Multi-Instance GPU — an NVIDIA technology that partitions a single GPU into multiple isolated instances
- **MIG_Profile**: A named configuration defining the size of a GPU partition (e.g., `1g.10gb`, `2g.20gb`, `4g.40gb`)
- **MIG_Instance**: A created GPU partition on a server, based on a MIG_Profile, representing an isolated GPU slice
- **Server_Record**: A row in the `servers` database table representing a registered platform server
- **Shared_GPU_Page**: The web interface page for managing MIG shared GPU configuration on a server
- **NVIDIA_Driver**: The NVIDIA GPU kernel driver package (nvidia-driver-550) required for GPU operation
- **NVIDIA_Container_Toolkit**: The nvidia-container-toolkit package that enables GPU access inside Docker containers
- **Admin_User**: A user with the `admin` role who has access to server management features
- **GPU_Device**: A physical NVIDIA GPU installed on a server

## Requirements

### Requirement 1: NVIDIA Driver Installation in Platform Init Script

**User Story:** As a platform administrator, I want the platform initialization script to install NVIDIA GPU drivers, so that servers with GPUs are ready for MIG partitioning.

#### Acceptance Criteria

1. WHEN the Platform_Init_Script executes, THE Platform_Init_Script SHALL install the `nvidia-driver-550` and `nvidia-utils-550` packages using `sudo apt install -y nvidia-driver-550 nvidia-utils-550`
2. WHEN the NVIDIA_Driver installation completes with exit code 0, THE Platform_Init_Script SHALL enable MIG mode by executing `sudo nvidia-smi -mig 1`
3. WHEN MIG mode is successfully enabled, THE Platform_Init_Script SHALL install the NVIDIA_Container_Toolkit using `sudo apt install -y nvidia-container-toolkit`
4. IF the NVIDIA_Driver installation command returns a non-zero exit code, THEN THE Platform_Init_Script SHALL skip the MIG mode enablement and the NVIDIA_Container_Toolkit installation, log a warning to stdout indicating the driver installation failure, and continue execution of the remaining setup steps
5. IF the MIG mode enablement command returns a non-zero exit code (GPU not present or incompatible), THEN THE Platform_Init_Script SHALL log a warning to stdout indicating MIG enablement failure and continue execution of the NVIDIA_Container_Toolkit installation and remaining setup steps
6. IF the NVIDIA_Container_Toolkit installation command returns a non-zero exit code, THEN THE Platform_Init_Script SHALL log a warning to stdout indicating the toolkit installation failure and continue execution of the remaining setup steps

### Requirement 2: GPU Access Verification

**User Story:** As a platform administrator, I want to verify that Docker containers can access the GPU after installation, so that I can confirm the GPU setup is operational.

#### Acceptance Criteria

1. WHEN the NVIDIA_Container_Toolkit installation completes with exit code 0, THE Platform_Init_Script SHALL verify GPU access by running `docker run --rm --gpus '"device=0"' nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi` with a timeout of 30 seconds
2. IF the GPU access verification command returns a non-zero exit code or exceeds the 30-second timeout, THEN THE Platform_Init_Script SHALL log a warning message indicating that GPU access from Docker is not functional and continue execution
3. WHEN the GPU access verification command returns exit code 0 within the 30-second timeout, THE Platform_Init_Script SHALL log a success message confirming Docker GPU access is operational

### Requirement 3: Server Shared GPU Database Flag

**User Story:** As a platform administrator, I want each server record to have a shared GPU enabled/disabled flag, so that I can track which servers have MIG GPU sharing activated.

#### Acceptance Criteria

1. THE Server_Record SHALL include a `shared_gpu_enabled` boolean field that defaults to `false`
2. WHEN an Admin_User sends a PUT request to the shared GPU enabled endpoint with a boolean value for a valid Server_Record, THE System SHALL update the `shared_gpu_enabled` field to match the requested value and return the updated server state
3. IF an Admin_User sends a PUT request to the shared GPU enabled endpoint for a server_id that does not exist, THEN THE System SHALL return an HTTP 404 response indicating the server was not found
4. IF a non-admin or unauthenticated user sends a request to the shared GPU enabled endpoint, THEN THE System SHALL return an HTTP 401 or 403 response without modifying any Server_Record

### Requirement 4: MIG Profile Storage

**User Story:** As a platform administrator, I want to store available MIG profiles in the database, so that the platform knows which GPU partitioning options are available per server.

#### Acceptance Criteria

1. THE System SHALL store MIG_Profile records with the following fields: profile name (VARCHAR up to 64 characters, e.g., `1g.10gb`), GPU memory size in GB (INTEGER, range 1 to 80), profile ID (VARCHAR up to 128 characters, nvidia-smi identifier), and associated server ID (foreign key to the servers table)
2. WHEN an Admin_User queries available MIG profiles for a server, THE System SHALL return all stored MIG_Profile records for that server ordered by profile name ascending
3. THE System SHALL enforce a foreign key relationship between MIG_Profile records and the Server_Record they belong to, with CASCADE deletion when the referenced server is removed
4. THE System SHALL enforce a unique constraint on the combination of profile name and server ID, preventing duplicate MIG profile entries for the same server
5. IF an Admin_User attempts to create a MIG_Profile referencing a server_id that does not exist, THEN THE System SHALL reject the operation with an error message indicating the server was not found

### Requirement 5: MIG Instance Storage

**User Story:** As a platform administrator, I want to store created MIG instances in the database, so that the platform tracks the current GPU partitioning state of each server.

#### Acceptance Criteria

1. THE System SHALL store MIG_Instance records with the following fields: instance UUID (from nvidia-smi, standard UUID format, max 36 characters, unique per server), associated MIG_Profile name (max 50 characters), GPU memory allocated in megabytes (integer, range 1 to 81920), server ID (foreign key to Server_Record), and creation timestamp
2. WHEN an Admin_User creates MIG instances on a server, THE System SHALL persist the resulting MIG_Instance records in the database within the same transaction as the successful CLI command execution
3. WHEN an Admin_User destroys MIG instances on a server, THE System SHALL remove all corresponding MIG_Instance records for that server from the database within the same transaction as the successful CLI command execution
4. THE System SHALL enforce a foreign key relationship between MIG_Instance records and the Server_Record they belong to, with CASCADE deletion so that removing a Server_Record removes all its associated MIG_Instance records
5. THE System SHALL enforce a unique constraint on the instance UUID per server, preventing duplicate MIG_Instance records for the same GPU partition
6. IF a MIG_Instance record cannot be persisted due to a database constraint violation (duplicate UUID or invalid server reference), THEN THE System SHALL return an error message indicating the specific constraint that was violated

### Requirement 6: List Available MIG Profiles via CLI

**User Story:** As a platform administrator, I want the system to list available MIG profiles from the GPU, so that I can see which partition sizes are supported on a given server.

#### Acceptance Criteria

1. WHEN an Admin_User requests the list of available MIG profiles for a specified server via the CLI, THE System SHALL execute `nvidia-smi mig -lgip` on the target server and return the result within 30 seconds
2. WHEN the command executes successfully, THE System SHALL parse the output and return a structured list of available MIG_Profile entries, where each entry contains: profile ID (integer), profile name (string), and memory size in MiB (integer)
3. IF the command fails because MIG is not enabled or a supported GPU is not present, THEN THE System SHALL return an error message indicating MIG is not available on that server
4. IF the target server is unreachable or the command times out after 30 seconds, THEN THE System SHALL return an error message indicating the server could not be contacted

### Requirement 7: Create MIG Instances via CLI

**User Story:** As a platform administrator, I want to create MIG GPU instances using profile IDs, so that I can partition the GPU into multiple isolated slices for shared usage.

#### Acceptance Criteria

1. WHEN an Admin_User submits a MIG instance creation request with a list of 1 to 7 profile IDs, THE System SHALL execute `sudo nvidia-smi mig -cgi <profile_ids> -C` on the target server and complete execution within 30 seconds
2. IF the MIG instance creation request contains an empty profile ID list or more than 7 profile IDs, THEN THE System SHALL reject the request and return an error message indicating the allowed range is 1 to 7 profile IDs
3. WHEN the MIG instance creation command succeeds (exit code 0), THE System SHALL execute `nvidia-smi -L` to retrieve the created instance details
4. WHEN the instance details are retrieved, THE System SHALL parse the output and store the resulting MIG_Instance records in the database, then return a success response containing the list of created MIG_Instance records to the Admin_User
5. IF the MIG instance creation command fails (non-zero exit code or exceeds 30-second timeout), THEN THE System SHALL return an error message including the command output to the Admin_User without modifying existing MIG_Instance records in the database
6. IF the `nvidia-smi -L` command fails after successful instance creation, THEN THE System SHALL return an error message indicating that instances were created but detail retrieval failed, and include the command output
7. IF the target server does not have `shared_gpu_enabled` set to `true`, THEN THE System SHALL reject the MIG instance creation request and return an error message indicating that shared GPU must be enabled first

### Requirement 8: Destroy MIG Instances via CLI

**User Story:** As a platform administrator, I want to destroy existing MIG instances, so that I can reconfigure the GPU partitioning.

#### Acceptance Criteria

1. WHEN an Admin_User submits a MIG instance destruction request for a server, THE System SHALL execute `sudo nvidia-smi mig -dci` followed by `sudo nvidia-smi mig -dgi` on the target server, with a timeout of 30 seconds per command
2. WHEN both destruction commands complete with exit code 0, THE System SHALL remove all MIG_Instance records associated with the target server from the database
3. IF the `sudo nvidia-smi mig -dci` command fails (non-zero exit code or timeout), THEN THE System SHALL skip the `sudo nvidia-smi mig -dgi` command and return an error message including the command output (up to 4096 characters) to the Admin_User without modifying any database records
4. IF the `sudo nvidia-smi mig -dci` command succeeds but `sudo nvidia-smi mig -dgi` fails (non-zero exit code or timeout), THEN THE System SHALL return an error message including the command output (up to 4096 characters) to the Admin_User without modifying any database records
5. IF no MIG_Instance records exist for the specified server, THEN THE System SHALL return an error message indicating no MIG instances are configured on the target server

### Requirement 9: Shared GPU Button in Server Management Page

**User Story:** As a platform administrator, I want a "Shared-GPU" button in the Server Management page, so that I can navigate to the MIG GPU configuration for a specific server.

#### Acceptance Criteria

1. WHILE the Admin_User is viewing the Server Management page, THE System SHALL display a "Shared-GPU" button in the actions column for each Server_Record in the servers grid
2. WHEN the Admin_User clicks the "Shared-GPU" button for a server, THE System SHALL navigate to the Shared_GPU_Page passing the corresponding server ID to identify the target server
3. THE System SHALL display the "Shared-GPU" button only for Admin_User sessions
4. IF a non-admin user accesses the Server Management page URL directly, THEN THE System SHALL not render the "Shared-GPU" button

### Requirement 10: Shared GPU Configuration Page

**User Story:** As a platform administrator, I want a dedicated page to enable and configure MIG shared GPU, so that I can manage GPU partitioning through the web interface.

#### Acceptance Criteria

1. WHEN the Shared_GPU_Page loads for a server, THE System SHALL display the current `shared_gpu_enabled` status of that server
2. WHEN the Shared_GPU_Page loads for a server, THE System SHALL display the list of existing MIG_Instance records for that server, showing for each instance: the instance UUID, MIG_Profile name, GPU memory allocated, and creation timestamp
3. THE Shared_GPU_Page SHALL provide a toggle control to enable or disable shared GPU for the server
4. THE Shared_GPU_Page SHALL provide a section to display available MIG_Profile options retrieved from the GPU, showing for each profile: the profile name, profile ID, and memory size
5. THE Shared_GPU_Page SHALL provide a control to select one or more MIG profiles and create GPU partitions
6. THE Shared_GPU_Page SHALL provide a control to destroy existing MIG instances on the server
7. WHEN the Admin_User enables shared GPU via the toggle, THE System SHALL update the `shared_gpu_enabled` field to `true` in the Server_Record and execute the MIG mode enablement command on the server
8. WHEN the Admin_User disables shared GPU via the toggle, THE System SHALL update the `shared_gpu_enabled` field to `false` in the Server_Record
9. IF the MIG mode enablement command fails after the Admin_User enables shared GPU via the toggle, THEN THE System SHALL display an error message indicating MIG mode could not be enabled and revert the `shared_gpu_enabled` field to `false`
10. WHEN the Admin_User creates MIG partitions via the page controls, THE System SHALL execute the instance creation command and update the displayed instance list upon success
11. IF the MIG instance creation or destruction command fails, THEN THE System SHALL display an error message indicating the operation failed and leave the displayed instance list unchanged

### Requirement 11: MIG Management API Endpoints

**User Story:** As a platform administrator, I want REST API endpoints for MIG management, so that the web interface can interact with the MIG subsystem.

#### Acceptance Criteria

1. THE System SHALL expose a `GET /api/servers/<server_id>/gpu/profiles` endpoint that returns the list of MIG profiles supported by the server's GPU hardware, including for each profile: profile ID, name, memory size, and compute capacity
2. THE System SHALL expose a `GET /api/servers/<server_id>/gpu/instances` endpoint that returns the list of currently active MIG instances on the server, including for each instance: instance ID, associated profile ID, status, and GPU memory allocated
3. WHEN an authenticated admin user sends a POST request to `/api/servers/<server_id>/gpu/instances` with a JSON body containing a non-empty list of valid profile IDs (maximum 7 entries), THE System SHALL create the corresponding MIG instances and return the created instance identifiers
4. WHEN an authenticated admin user sends a DELETE request to `/api/servers/<server_id>/gpu/instances`, THE System SHALL destroy all MIG instances on the specified server and return a confirmation with the count of destroyed instances
5. THE System SHALL expose a `PUT /api/servers/<server_id>/gpu/enabled` endpoint that sets the shared GPU enabled flag to the boolean value provided in the request body
6. IF an unauthenticated user calls any GPU management endpoint, THEN THE System SHALL return HTTP 401
7. IF an authenticated non-admin user calls any GPU management endpoint, THEN THE System SHALL return HTTP 403
8. IF the server_id does not correspond to an existing server, THEN THE System SHALL return HTTP 404 for any GPU management endpoint
9. IF the POST request to create MIG instances contains an empty profile ID list or any profile ID that does not exist in the server's available profiles, THEN THE System SHALL return HTTP 400 with an error message indicating the validation failure

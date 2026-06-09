#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper function
print_step() {
    echo -e "${BLUE}>${NC} ${GREEN}$1${NC}"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo -e "${BLUE}+==========================================+${NC}"
echo -e "${BLUE}|${NC}   ai-powered-store Platform Setup    ${BLUE}|${NC}"
echo -e "${BLUE}+==========================================+${NC}"
echo ""

# Install Python and pip
print_step "Installing system dependencies..."
sudo apt update > /dev/null 2>&1
sudo apt --fix-broken install -y > /dev/null 2>&1
sudo apt install -y python3 python3-pip python3-venv net-tools unzip > /dev/null 2>&1
print_success "System dependencies installed"

# Install Amazon Kiro CLI Chat
print_step "Installing Amazon Kiro CLI..."
curl -fsSL https://cli.kiro.dev/install | bash > /dev/null 2>&1
print_success "Amazon Kiro CLI installed"

# Install OVH shai
print_step "Installing OVH CLI..."
curl -fsSL https://raw.githubusercontent.com/ovh/shai/main/install.sh | sh > /dev/null 2>&1
echo 'export PATH="~/.local/bin:$PATH"' >> ~/.bashrc
print_success "OVH CLI installed"

# Install AWS CLI
print_step "Installing AWS CLI..."
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
sudo ./aws/install > /dev/null 2>&1
rm -rf aws awscliv2.zip
print_success "AWS CLI installed"

# Install Terraform
print_step "Installing Terraform..."
curl -s "https://releases.hashicorp.com/terraform/1.14.5/terraform_1.14.5_linux_amd64.zip" -o "terraform.zip"
unzip -q terraform.zip
sudo mv terraform /usr/local/bin/
rm -f terraform.zip
print_success "Terraform installed"

# Configure network interface priorities
print_step "Configuring network interface priorities..."
if [ -f /etc/netplan/*.yaml ]; then
    NETPLAN_FILE=$(ls /etc/netplan/*.yaml | head -1)
    sudo cp $NETPLAN_FILE ${NETPLAN_FILE}.backup
    
    # Detect interfaces and their IPs
    INTERFACES=$(ip -o link show | awk -F': ' '{print $2}' | grep -E '^e' | grep -v '@')
    PUBLIC_IF=""
    PRIVATE_IF=""
    
    for iface in $INTERFACES; do
        IP=$(ip -4 addr show $iface | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
        if [ -n "$IP" ]; then
            # Check if IP is private (10.x, 172.16-31.x, 192.168.x)
            if [[ $IP =~ ^10\. ]] || [[ $IP =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]] || [[ $IP =~ ^192\.168\. ]]; then
                PRIVATE_IF=$iface
            else
                PUBLIC_IF=$iface
            fi
        fi
    done
    
    # Generate netplan config
    echo "network:" | sudo tee $NETPLAN_FILE > /dev/null
    echo "  version: 2" | sudo tee -a $NETPLAN_FILE > /dev/null
    echo "  ethernets:" | sudo tee -a $NETPLAN_FILE > /dev/null
    
    for iface in $INTERFACES; do
        echo "    $iface:" | sudo tee -a $NETPLAN_FILE > /dev/null
        echo "      dhcp4: true" | sudo tee -a $NETPLAN_FILE > /dev/null
        if [ "$iface" = "$PUBLIC_IF" ]; then
            echo "      dhcp4-overrides:" | sudo tee -a $NETPLAN_FILE > /dev/null
            echo "        route-metric: 50" | sudo tee -a $NETPLAN_FILE > /dev/null
        elif [ "$iface" = "$PRIVATE_IF" ]; then
            echo "      dhcp4-overrides:" | sudo tee -a $NETPLAN_FILE > /dev/null
            echo "        route-metric: 200" | sudo tee -a $NETPLAN_FILE > /dev/null
        fi
    done
    
    sudo netplan apply > /dev/null 2>&1
    print_success "Network priorities configured (public: 50, private: 200)"
else
    print_warning "Netplan not found, skipping network configuration"
fi

# Install Docker
print_step "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh > /dev/null 2>&1
sudo usermod -aG docker $USER
sudo curl -sL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
rm -f get-docker.sh
print_success "Docker installed"

# Install NVIDIA GPU Drivers and MIG Support
print_step "Installing NVIDIA GPU drivers..."
sudo apt install -y nvidia-driver-550 nvidia-utils-550 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    print_success "NVIDIA drivers installed"
    
    print_step "Enabling MIG mode..."
    sudo nvidia-smi -mig 1 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "MIG mode enabled"
    else
        print_warning "MIG mode could not be enabled (GPU may not support MIG)"
    fi
    
    print_step "Installing NVIDIA Container Toolkit..."
    sudo apt install -y nvidia-container-toolkit > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "NVIDIA Container Toolkit installed"
        
        print_step "Verifying Docker GPU access..."
        timeout 30 docker run --rm --gpus '"device=0"' nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            print_success "Docker GPU access verified"
        else
            print_warning "Docker GPU access verification failed (GPU may not be available)"
        fi
    else
        print_warning "NVIDIA Container Toolkit installation failed"
    fi
else
    print_warning "NVIDIA driver installation failed (no GPU or incompatible hardware), skipping GPU setup"
fi

# Configure AWS
print_step "Configuring AWS credentials..."
mkdir -p ~/.aws
cat > ~/.aws/config <<EOF
[profile OVH-SWAUTOMORPH]
region = gra
output = json
EOF

cat > ~/.aws/credentials <<EOF
[OVH-SWAUTOMORPH]
aws_access_key_id = XXX
aws_secret_access_key = YYY
endpoint_url = https://s3.gra.io.cloud.ovh.net/
signature_version = s3v4
EOF

export AWS_DEFAULT_PROFILE=OVH-SWAUTOMORPH
export AWS_ENDPOINT_URL_S3=https://s3.gra.io.cloud.ovh.net/
print_success "AWS credentials configured"

# Clone repository
print_step "Cloning opcp-ai-powered-store repository..."
git clone https://github.com/Sam9682/opcp-ai-powered-store.git > /dev/null 2>&1
cd opcp-ai-powered-store
git submodule update --init --recursive > /dev/null 2>&1
print_success "Repository cloned"

# Setup Python environment
print_step "Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
print_success "Python environment ready"

# Final setup
print_step "Final configuration..."
mkdir -p logs
chmod +x setup_modsecurity_config.sh
cd ~
mkdir -p deployments
cd deployments
mkdir -p admin
print_success "Configuration complete"

echo ""
echo -e "${GREEN}[OK] Installation completed successfully!${NC}"
echo ""
print_warning "Don't forget to :"
print_warning "     - modify ./conf/deploy.ini with your platform settings, PLTF_NAME and DOMAIN values"
print_warning "     - add ssl certificate in ~/opcp-ai-powered-store/ssl/fullchain_domain.crt for nginx https"
print_warning "     - add ssl private key in ~/opcp-ai-powered-store/ssl/privateKey_domain.key for nginx https"
print_warning "     - enter aws_access_key_id & aws_secret_access_key in ~/.aws/credentials for s3 synchronization"

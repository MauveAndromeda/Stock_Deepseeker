"""
Deployment Script
Deploys the trading system to production
"""

import sys
import os
import subprocess
from pathlib import Path
from loguru import logger


def run_command(cmd, cwd=None):
    """Run shell command"""
    logger.info(f"Running: {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logger.error(f"Command failed: {result.stderr}")
        return False
    
    logger.info(result.stdout)
    return True


def check_dependencies():
    """Check required dependencies"""
    logger.info("Checking dependencies...")
    
    required = ['python3', 'pip', 'docker', 'docker-compose']
    
    for dep in required:
        if not run_command(f"which {dep}"):
            logger.error(f"Required dependency not found: {dep}")
            return False
    
    logger.info("All dependencies found")
    return True


def install_python_packages():
    """Install Python packages"""
    logger.info("Installing Python packages...")
    
    if not run_command("pip install -r requirements.txt"):
        logger.error("Failed to install Python packages")
        return False
    
    logger.info("Python packages installed")
    return True


def setup_environment():
    """Setup environment variables"""
    logger.info("Setting up environment...")
    
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text())
        logger.warning("Created .env from .env.example - please update with your API keys")
    
    return True


def build_docker_containers():
    """Build Docker containers"""
    logger.info("Building Docker containers...")
    
    if not run_command("docker-compose build"):
        logger.error("Failed to build Docker containers")
        return False
    
    logger.info("Docker containers built")
    return True


def start_services():
    """Start all services"""
    logger.info("Starting services...")
    
    if not run_command("docker-compose up -d"):
        logger.error("Failed to start services")
        return False
    
    logger.info("Services started")
    return True


def run_migrations():
    """Run database migrations"""
    logger.info("Running database migrations...")
    
    if not run_command("python scripts/setup/init_database.py"):
        logger.error("Failed to run migrations")
        return False
    
    logger.info("Migrations complete")
    return True


def verify_deployment():
    """Verify deployment"""
    logger.info("Verifying deployment...")
    
    # Check if containers are running
    if not run_command("docker-compose ps"):
        logger.error("Container check failed")
        return False
    
    logger.info("Deployment verified")
    return True


def main():
    """Main deployment function"""
    logger.info("Starting deployment...")
    
    steps = [
        ("Check dependencies", check_dependencies),
        ("Install packages", install_python_packages),
        ("Setup environment", setup_environment),
        ("Build Docker containers", build_docker_containers),
        ("Start services", start_services),
        ("Run migrations", run_migrations),
        ("Verify deployment", verify_deployment),
    ]
    
    for name, func in steps:
        logger.info(f"Step: {name}")
        if not func():
            logger.error(f"Deployment failed at step: {name}")
            return False
    
    logger.info("Deployment complete!")
    logger.info("System is ready to use")
    logger.info("Run 'python src/main.py' to start trading")
    
    return True


if __name__ == "__main__":
    main()

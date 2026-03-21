"""
Example test file for AI Novel System.
This demonstrates the testing structure for the project.
"""

import pytest


def test_example():
    """Example test that always passes."""
    assert True


def test_docker_compose_exists():
    """Test that docker-compose-cn.yml exists."""
    import os
    assert os.path.exists('docker-compose-cn.yml')
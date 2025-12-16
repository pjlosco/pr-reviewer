"""
Tests for app.py entry point

These tests verify the command-line interface and entry point behavior.
Following TDD: tests define expected behavior before implementation.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock, Mock
from io import StringIO


class TestAppMain:
    """Tests for the main() function in app.py"""
    
    def test_main_with_valid_pr_url(self, mock_env_vars):
        """
        Test that main() successfully calls run_review_agent with valid PR URL.
        
        Expected behavior:
        - Parses --pr-url argument
        - Calls run_review_agent with correct URL
        - Exits with code 0 on success
        """
        test_args = ["app.py", "--pr-url", "https://github.com/owner/repo/pull/123"]
        
        with patch("sys.argv", test_args):
            with patch("app.run_review_agent") as mock_run:
                mock_run.return_value = None
                
                from app import main
                
                # Should exit with code 0 on success
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                # Verify run_review_agent was called with correct URL
                mock_run.assert_called_once_with(
                    pr_url="https://github.com/owner/repo/pull/123",
                    verbose=False
                )
    
    def test_main_with_verbose_flag(self, mock_env_vars):
        """
        Test that main() passes verbose flag correctly.
        
        Expected behavior:
        - --verbose flag sets verbose=True
        - Passes verbose to run_review_agent
        """
        test_args = ["app.py", "--pr-url", "https://github.com/owner/repo/pull/123", "--verbose"]
        
        with patch("sys.argv", test_args):
            with patch("app.run_review_agent") as mock_run:
                mock_run.return_value = None
                
                from app import main
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                mock_run.assert_called_once_with(
                    pr_url="https://github.com/owner/repo/pull/123",
                    verbose=True
                )
    
    def test_main_missing_pr_url(self, mock_env_vars):
        """
        Test that main() fails when --pr-url is missing.
        
        Expected behavior:
        - Raises SystemExit with non-zero code
        - Prints error message about missing required argument
        """
        test_args = ["app.py"]
        
        with patch("sys.argv", test_args):
            with patch("sys.stderr", new=StringIO()):
                from app import main
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code != 0
    
    def test_main_with_help_flag(self, mock_env_vars):
        """
        Test that main() shows help text when --help is used.
        
        Expected behavior:
        - Prints help text
        - Exits with code 0
        """
        test_args = ["app.py", "--help"]
        
        with patch("sys.argv", test_args):
            with patch("sys.stdout", new=StringIO()) as mock_stdout:
                from app import main
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                # Help text contains "AI-powered code review agent"
                help_text = mock_stdout.getvalue()
                assert "code review agent" in help_text.lower() or "pr_url" in help_text.lower()
    
    def test_main_handles_agent_exception(self, mock_env_vars):
        """
        Test that main() handles exceptions from run_review_agent gracefully.
        
        Expected behavior:
        - Catches exceptions from run_review_agent
        - Prints error message to stderr
        - Exits with code 1
        """
        test_args = ["app.py", "--pr-url", "https://github.com/owner/repo/pull/123"]
        
        with patch("sys.argv", test_args):
            with patch("app.run_review_agent") as mock_run:
                import io
                mock_stderr = io.StringIO()
                
                with patch("sys.stderr", mock_stderr):
                    mock_run.side_effect = Exception("Test error")
                    
                    from app import main
                    
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    
                    assert exc_info.value.code == 1
                    # Error message should contain "Test error" or "Error:"
                    stderr_output = mock_stderr.getvalue()
                    assert "Test error" in stderr_output or "Error:" in stderr_output
    
    def test_main_verbose_shows_traceback(self, mock_env_vars):
        """
        Test that main() shows traceback when --verbose and exception occurs.
        
        Expected behavior:
        - With --verbose, shows full traceback
        - Without --verbose, shows only error message
        """
        test_args = ["app.py", "--pr-url", "https://github.com/owner/repo/pull/123", "--verbose"]
        
        with patch("sys.argv", test_args):
            with patch("app.run_review_agent") as mock_run:
                import io
                mock_stderr = io.StringIO()
                
                with patch("sys.stderr", mock_stderr):
                    mock_run.side_effect = Exception("Test error")
                    
                    from app import main
                    
                    with pytest.raises(SystemExit):
                        main()
                    
                    # With verbose, should show traceback
                    stderr_output = mock_stderr.getvalue()
                    assert "Traceback" in stderr_output or "Test error" in stderr_output


class TestAppModule:
    """Tests for app.py as a module"""
    
    def test_app_can_be_imported(self):
        """Test that app.py can be imported without errors."""
        import app
        assert hasattr(app, "main")
    
    def test_app_has_main_function(self):
        """Test that app.py has a main() function."""
        from app import main
        assert callable(main)


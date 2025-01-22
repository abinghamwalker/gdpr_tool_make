import pytest
import json
import sys
from unittest.mock import patch, Mock
from src.run_locally import main

class TestRunLocally:
    def test_processing_error(self, capsys, tmpdir):
        """Test error during file processing."""
        test_file = tmpdir.join("test.csv")
        test_file.write("name,email\nJohn,john@test.com")

        with patch('src.run_locally.MultiFormatObfuscator') as mock_obfuscator:
            mock_instance = Mock()
            mock_instance.process_request.side_effect = Exception("Processing failed")
            mock_obfuscator.return_value = mock_instance
            
            with patch.object(sys, 'argv', [
                'script.py',
                str(test_file),
                '["name", "email"]'
            ]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                # Check the exit code
                assert exc_info.value.code == 1
                
                # Check the error message
                captured = capsys.readouterr()
                assert "Error processing file: Processing failed" in captured.out

    def test_usage_instructions(self, capsys):
        """Test usage instructions when incorrect arguments are provided."""
        with patch.object(sys, 'argv', ['script.py']):  # No arguments
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Check the exit code
            assert exc_info.value.code == 1
            
            # Capture and verify the output
            captured = capsys.readouterr()
            assert "Usage: python test_obfuscator.py <input_file> <pii_fields>" in captured.out

    def test_invalid_json(self, capsys, tmpdir):
        """Test handling of invalid JSON for PII fields."""
        test_file = tmpdir.join("test.csv")
        test_file.write("name,email\nJohn,john@test.com")

        with patch.object(sys, 'argv', [
            'script.py',
            str(test_file),
            'invalid_json'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Check the exit code
            assert exc_info.value.code == 1
            
            # Capture and verify the output
            captured = capsys.readouterr()
            assert "Invalid JSON format for PII fields." in captured.out
    
    def test_file_not_found(self, capsys):
        """Test handling of missing input file."""
        with patch.object(sys, 'argv', [
            'script.py',
            'nonexistent_file.csv',
            '["name", "email"]'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Check the exit code
            assert exc_info.value.code == 1
            
            # Capture and verify the output
            captured = capsys.readouterr()
            assert "Input file not found:" in captured.out

    def test_successful_execution(self, capsys, tmpdir):
        """Test successful execution of the obfuscator."""
        test_file = tmpdir.join("test.csv")
        test_file.write("name,email\nJohn,john@test.com")

        mock_result = {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Successfully processed and overwritten local file: {str(test_file)}",
                "format": "csv"
            })
        }

        with patch('src.run_locally.MultiFormatObfuscator') as mock_obfuscator:
            mock_instance = Mock()
            mock_instance.process_request.return_value = mock_result
            mock_obfuscator.return_value = mock_instance

            with patch.object(sys, 'argv', [
                'script.py',
                str(test_file),
                '["name", "email"]'
            ]):
                main()
                
                # Verify the output
                captured = capsys.readouterr()
                assert "Successfully processed and overwritten local file:" in captured.out

    def test_complex_pii_fields(self, capsys, tmpdir):
        """Test processing with complex PII fields JSON."""
        test_file = tmpdir.join("test.csv")
        test_file.write("name,email,address\nJohn,john@test.com,123 St")
        
        complex_pii = json.dumps([
            "name",
            "email",
            "address"
        ])
        
        mock_result = {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Successfully processed and overwritten local file: {str(test_file)}",
                "format": "csv"
            })
        }
        
        with patch('src.run_locally.MultiFormatObfuscator') as mock_obfuscator:
            mock_instance = Mock()
            mock_instance.process_request.return_value = mock_result
            mock_obfuscator.return_value = mock_instance
            
            with patch.object(sys, 'argv', [
                'script.py',
                str(test_file),
                complex_pii
            ]):
                main()
                
                # Verify the mock was called with correct arguments
                assert mock_instance.process_request.call_count == 1
                call_args = mock_instance.process_request.call_args[0][0]
                assert "pii_fields" in call_args
                assert len(call_args["pii_fields"]) == 3
                assert all(field in call_args["pii_fields"] 
                          for field in ["name", "email", "address"])
import json
import os
import sys

from src.obfuscator import MultiFormatObfuscator


def main():
    if len(sys.argv) != 3:
        sys.exit(1)

    input_file = sys.argv[1]
    try:
        pii_fields = json.loads(sys.argv[2])
    except json.JSONDecodeError:
        print(
            "Invalid JSON format for PII fields. "
            "Please provide a valid JSON array of field names."
        )
        sys.exit(1)

    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        sys.exit(1)

    obfuscator = MultiFormatObfuscator()

    event = {"file_to_obfuscate": input_file, "pii_fields": pii_fields}
    try:
        result = obfuscator.process_request(event)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

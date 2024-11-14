import unittest
import os
from pathlib import Path
from datetime import datetime
from .msgpack_output import (
    MessagePackError,
    MessagePackConfig,
    MessagePackEncoder,
    MessagePackDecoder,
    validate_msgpack_file,
    output_to_msgpack,
    output_to_msgpack_stream
)

class TestMsgpackValidation(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_output.msgpack"
        self.test_data = {
            "files": [
                {
                    "path": "/test/file1.txt",
                    "size": 1024,
                    "mime_type": "text/plain",
                    "hash": "abc123",
                    "last_modified": datetime.now().timestamp(),
                    "metadata": {"encoding": "utf-8"}
                },
                {
                    "path": "/test/file2.jpg",
                    "size": 2048,
                    "mime_type": "image/jpeg",
                    "hash": "def456",
                    "last_modified": datetime.now().timestamp(),
                    "metadata": {"dimensions": "800x600"}
                }
            ],
            "summary": {
                "total_files": 2,
                "total_size": 3072,
                "timestamp": datetime.now().timestamp()
            }
        }

    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_valid_msgpack_file(self):
        """Test validation of a valid MessagePack file"""
        # Write test data
        output_to_msgpack(self.test_data, self.test_file)
        
        # Validate the file
        self.assertTrue(validate_msgpack_file(self.test_file))
        
        # Read and verify content
        decoder = MessagePackDecoder()
        with open(self.test_file, 'rb') as f:
            decoded_data = decoder.decode_stream(f.read())
        
        # Since it's a single object written, it will be in a list with one item
        self.assertEqual(len(decoded_data), 1)
        decoded_data = decoded_data[0]  # Get the actual data
        self.assertEqual(len(decoded_data["files"]), 2)
        self.assertEqual(decoded_data["files"][0]["path"], "/test/file1.txt")
        self.assertEqual(decoded_data["summary"]["total_files"], 2)

    def test_invalid_msgpack_file(self):
        """Test validation of an invalid MessagePack file"""
        # Write invalid data
        with open(self.test_file, 'wb') as f:
            f.write(b'invalid msgpack data')
        
        # Validation should fail
        self.assertFalse(validate_msgpack_file(self.test_file))

    def test_empty_msgpack_file(self):
        """Test validation of an empty MessagePack file"""
        # Create empty file
        Path(self.test_file).touch()
        
        # Validation should fail
        self.assertFalse(validate_msgpack_file(self.test_file))

    def test_streaming_validation(self):
        """Test validation of streamed MessagePack data"""
        def data_generator():
            for item in self.test_data["files"]:
                yield item

        # Write test data using streaming
        output_to_msgpack_stream(data_generator(), self.test_file)
        
        # Validate the file
        self.assertTrue(validate_msgpack_file(self.test_file))
        
        # Read and verify content
        decoder = MessagePackDecoder()
        with open(self.test_file, 'rb') as f:
            decoded_data = decoder.decode_stream(f.read())
        
        self.assertTrue(isinstance(decoded_data, list))
        self.assertEqual(len(decoded_data), 2)  # Should have two entries
        self.assertEqual(decoded_data[0]["path"], "/test/file1.txt")
        self.assertEqual(decoded_data[1]["path"], "/test/file2.jpg")

    def test_large_data_validation(self):
        """Test validation of large MessagePack data"""
        # Create large test data
        large_data = {
            "files": [
                {
                    "path": f"/test/file{i}.txt",
                    "size": 1024 * i,
                    "mime_type": "text/plain",
                    "hash": f"hash{i}",
                    "last_modified": datetime.now().timestamp(),
                    "metadata": {"index": i}
                }
                for i in range(1000)  # Create 1000 test files
            ]
        }
        
        # Write and validate large data
        output_to_msgpack(large_data, self.test_file)
        self.assertTrue(validate_msgpack_file(self.test_file))
        
        # Verify file size
        file_size = os.path.getsize(self.test_file)
        self.assertGreater(file_size, 100000)  # Should be >100KB

    def test_special_types_validation(self):
        """Test validation of MessagePack data with special types"""
        special_data = {
            "datetime": datetime.now(),
            "path": Path("/test/path"),
            "bytes": b"binary data",
            "set": {1, 2, 3},
            "nested": {
                "list": [1, 2, 3],
                "dict": {"key": "value"}
            }
        }
        
        # Write and validate data with special types
        output_to_msgpack(special_data, self.test_file)
        self.assertTrue(validate_msgpack_file(self.test_file))
        
        # Verify special types are handled correctly
        decoder = MessagePackDecoder()
        with open(self.test_file, 'rb') as f:
            decoded_data = decoder.decode_stream(f.read())[0]  # Get first item since it's a single object
        
        self.assertTrue(isinstance(decoded_data["datetime"], datetime))
        self.assertTrue(isinstance(decoded_data["path"], str))
        self.assertEqual(decoded_data["set"], [1, 2, 3])

    def test_multiple_entries_stream(self):
        """Test writing and reading multiple entries in a stream"""
        entries = [
            {"id": 1, "name": "Entry 1"},
            {"id": 2, "name": "Entry 2"},
            {"id": 3, "name": "Entry 3"}
        ]
        
        def entry_generator():
            for entry in entries:
                yield entry
        
        # Write entries using stream
        output_to_msgpack_stream(entry_generator(), self.test_file)
        
        # Validate the file
        self.assertTrue(validate_msgpack_file(self.test_file))
        
        # Read and verify all entries
        decoder = MessagePackDecoder()
        with open(self.test_file, 'rb') as f:
            decoded_entries = decoder.decode_stream(f.read())
        
        self.assertEqual(len(decoded_entries), len(entries))
        for original, decoded in zip(entries, decoded_entries):
            self.assertEqual(original, decoded)

if __name__ == '__main__':
    unittest.main()

# ─────────────────────────────────────────────
#  CHUD — test_bytecode_serialization.py
#  Tests binary bytecode serialization (.chudc),
#  CRC32 integrity validation, and VM execution parity.
# ─────────────────────────────────────────────

import os
from interpreter import interpret
from compiler import compile_source
from vm import VM, run_source
from bytecode_serializer import (
    serialize_chunk, deserialize_chunk,
    compile_source_to_chudc, load_chudc_file,
    SerializationError, MAGIC_BYTES
)


def test_serialization_roundtrip_and_parity():
    source = '''
make bubble_sort(arr) {
    let n = len(arr)
    loop let i = 0; i < n; i = i + 1 {
        loop let j = 0; j < n - i - 1; j = j + 1 {
            check arr[j] > arr[j + 1] {
                let temp = arr[j]
                arr[j] = arr[j + 1]
                arr[j + 1] = temp
            }
        }
    }
    return arr
}

let numbers = [55, 12, 88, 1, 34, 7]
yap "Original: " + numbers
let sorted = bubble_sort(numbers)
yap "Sorted: " + sorted
yap "Boolean check: " + (W and not L)
yap "Arithmetic: " + (100 % 30 + 5 * 2)
'''

    # 1. Compile to Chunk
    chunk = compile_source(source)

    # 2. Serialize to binary
    bin_data = serialize_chunk(chunk)
    assert bin_data.startswith(MAGIC_BYTES), "Magic header missing in serialized binary"
    print(f"[OK] Serialized to binary payload ({len(bin_data)} bytes)")

    # 3. Deserialize back to Chunk
    reconstructed_chunk = deserialize_chunk(bin_data)
    assert len(reconstructed_chunk.instructions) == len(chunk.instructions), "Instruction count mismatch"
    assert len(reconstructed_chunk.constants) == len(chunk.constants), "Constants count mismatch"

    # 4. Execute reconstructed chunk on VM
    vm = VM()
    res = vm.run(reconstructed_chunk)
    assert res["success"] is True, f"VM execution of deserialized chunk failed: {res['error']}"

    interp_res = interpret(source)
    assert res["output"] == interp_res["output"], (
        f"Output mismatch.\n  reconstructed VM: {res['output']}\n  interpreter: {interp_res['output']}"
    )
    print(f"[OK] Deserialized chunk executed with 100% parity! Output: {res['output']}")

    # 5. File serialization roundtrip
    test_chudc = "test_game.chudc"
    compile_source_to_chudc(source, test_chudc)
    assert os.path.exists(test_chudc), "Failed to write .chudc file"

    file_chunk = load_chudc_file(test_chudc)
    file_vm = VM()
    file_res = file_vm.run(file_chunk)
    assert file_res["output"] == interp_res["output"]
    print("[OK] Disk .chudc file load & execution verified successfully!")

    # 6. CRC32 Corrupted File Rejection Test
    with open(test_chudc, "rb") as f:
        corrupted_data = bytearray(f.read())

    # Corrupt a byte in the payload
    corrupted_data[-1] ^= 0xFF
    try:
        deserialize_chunk(bytes(corrupted_data))
        assert False, "Failed to catch CRC32 corrupted bytecode!"
    except SerializationError as e:
        print(f"[OK] CRC32 corruption caught safely: {e}")

    # Cleanup
    if os.path.exists(test_chudc):
        os.remove(test_chudc)


if __name__ == '__main__':
    test_serialization_roundtrip_and_parity()
    print("\n[CHUD] ALL PHASE 3 BINARY SERIALIZATION TESTS PASSED!")

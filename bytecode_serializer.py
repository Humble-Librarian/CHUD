# ─────────────────────────────────────────────
#  CHUD — bytecode_serializer.py
#  Binary Bytecode Serialization & Deserialization
#  for CHUD (.chudc) Distribution Files.
#  Zero external dependencies — pure Python stdlib.
# ─────────────────────────────────────────────

import struct
import zlib
import io
from bytecode import Chunk, Instruction, OpCode, CHUDFunctionProto
from compiler import compile_source


MAGIC_BYTES = b"CHUD"       # 0x43485544
FORMAT_VERSION = 1          # uint16

# ── Type tags for Constant Pool ──
TAG_INT    = 1
TAG_FLOAT  = 2
TAG_STRING = 3
TAG_BOOL   = 4
TAG_NONE   = 5
TAG_PROTO  = 6

# ── Argument tags for Instructions ──
ARG_NONE          = 0
ARG_INT           = 1
ARG_STR           = 2
ARG_TUPLE_STR_INT = 3


class SerializationError(Exception):
    """Raised when bytecode binary is corrupt, invalid, or version mismatch."""
    pass


class BytecodeSerializer:
    """Serializes in-memory Chunk objects to binary bytes."""

    def serialize_chunk(self, chunk: Chunk) -> bytes:
        buf = io.BytesIO()

        # 1. Constant Pool
        constants = chunk.constants
        buf.write(struct.pack("<I", len(constants)))
        for const in constants:
            self._write_constant(buf, const)

        # 2. Instruction Stream
        instructions = chunk.instructions
        buf.write(struct.pack("<I", len(instructions)))
        for instr in instructions:
            self._write_instruction(buf, instr)

        return buf.getvalue()

    def _write_constant(self, buf: io.BytesIO, val):
        if val is None:
            buf.write(struct.pack("<B", TAG_NONE))
        elif isinstance(val, bool):
            buf.write(struct.pack("<B?", TAG_BOOL, val))
        elif isinstance(val, int):
            buf.write(struct.pack("<Bq", TAG_INT, val))
        elif isinstance(val, float):
            buf.write(struct.pack("<Bd", TAG_FLOAT, val))
        elif isinstance(val, str):
            encoded = val.encode('utf-8')
            buf.write(struct.pack("<BI", TAG_STRING, len(encoded)))
            buf.write(encoded)
        elif isinstance(val, CHUDFunctionProto):
            name_bytes = val.name.encode('utf-8')
            inner_chunk_bytes = self.serialize_chunk(val.chunk)
            buf.write(struct.pack("<BI", TAG_PROTO, len(name_bytes)))
            buf.write(name_bytes)
            # Parameters
            buf.write(struct.pack("<I", len(val.parameters)))
            for param in val.parameters:
                p_bytes = param.encode('utf-8')
                buf.write(struct.pack("<I", len(p_bytes)))
                buf.write(p_bytes)
            # Nested chunk payload
            buf.write(struct.pack("<I", len(inner_chunk_bytes)))
            buf.write(inner_chunk_bytes)
        else:
            raise SerializationError(f"Unsupported constant type in pool: {type(val).__name__}")

    def _write_instruction(self, buf: io.BytesIO, instr: Instruction):
        op_id = OpCode.OPCODE_TO_ID.get(instr.op)
        if op_id is None:
            raise SerializationError(f"Unknown OpCode for serialization: {instr.op}")
        buf.write(struct.pack("<B", op_id))

        arg = instr.arg
        if arg is None:
            buf.write(struct.pack("<B", ARG_NONE))
        elif isinstance(arg, int):
            buf.write(struct.pack("<Bq", ARG_INT, arg))
        elif isinstance(arg, str):
            encoded = arg.encode('utf-8')
            buf.write(struct.pack("<BI", ARG_STR, len(encoded)))
            buf.write(encoded)
        elif isinstance(arg, tuple) and len(arg) == 2 and isinstance(arg[0], str) and isinstance(arg[1], int):
            encoded = arg[0].encode('utf-8')
            buf.write(struct.pack("<BII", ARG_TUPLE_STR_INT, len(encoded), arg[1]))
            buf.write(encoded)
        else:
            raise SerializationError(f"Unsupported instruction argument for '{instr.op}': {repr(arg)}")

        line_no = instr.line if instr.line is not None else 0
        buf.write(struct.pack("<I", line_no))

    def serialize_file(self, chunk: Chunk) -> bytes:
        """Serializes a Chunk with standard CHUD binary header and CRC32 checksum."""
        payload = self.serialize_chunk(chunk)
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        header = struct.pack("<4sHI", MAGIC_BYTES, FORMAT_VERSION, crc)
        return header + payload


class BytecodeDeserializer:
    """Deserializes binary bytes back into a Chunk object."""

    def deserialize_chunk(self, data: bytes) -> Chunk:
        buf = io.BytesIO(data)
        return self._read_chunk(buf)

    def _read_chunk(self, buf: io.BytesIO) -> Chunk:
        chunk = Chunk()

        # 1. Constant Pool
        raw_count = buf.read(4)
        if len(raw_count) < 4:
            raise SerializationError("Unexpected EOF reading constant pool size.")
        const_count = struct.unpack("<I", raw_count)[0]

        for _ in range(const_count):
            chunk.constants.append(self._read_constant(buf))

        # 2. Instruction Stream
        raw_instr_count = buf.read(4)
        if len(raw_instr_count) < 4:
            raise SerializationError("Unexpected EOF reading instruction stream size.")
        instr_count = struct.unpack("<I", raw_instr_count)[0]

        for _ in range(instr_count):
            chunk.instructions.append(self._read_instruction(buf))

        return chunk

    def _read_constant(self, buf: io.BytesIO):
        tag_byte = buf.read(1)
        if not tag_byte:
            raise SerializationError("Unexpected EOF reading constant tag.")
        tag = struct.unpack("<B", tag_byte)[0]

        if tag == TAG_NONE:
            return None
        elif tag == TAG_BOOL:
            return struct.unpack("<?", buf.read(1))[0]
        elif tag == TAG_INT:
            return struct.unpack("<q", buf.read(8))[0]
        elif tag == TAG_FLOAT:
            return struct.unpack("<d", buf.read(8))[0]
        elif tag == TAG_STRING:
            str_len = struct.unpack("<I", buf.read(4))[0]
            return buf.read(str_len).decode('utf-8')
        elif tag == TAG_PROTO:
            name_len = struct.unpack("<I", buf.read(4))[0]
            name = buf.read(name_len).decode('utf-8')
            param_count = struct.unpack("<I", buf.read(4))[0]
            params = []
            for _ in range(param_count):
                p_len = struct.unpack("<I", buf.read(4))[0]
                params.append(buf.read(p_len).decode('utf-8'))
            inner_chunk_len = struct.unpack("<I", buf.read(4))[0]
            inner_chunk_data = buf.read(inner_chunk_len)
            inner_chunk = self.deserialize_chunk(inner_chunk_data)
            return CHUDFunctionProto(name, params, inner_chunk)
        else:
            raise SerializationError(f"Unknown constant pool tag: {tag}")

    def _read_instruction(self, buf: io.BytesIO) -> Instruction:
        op_byte = buf.read(1)
        if not op_byte:
            raise SerializationError("Unexpected EOF reading instruction opcode.")
        op_id = struct.unpack("<B", op_byte)[0]
        op = OpCode.ID_TO_OPCODE.get(op_id)
        if op is None:
            raise SerializationError(f"Unknown OpCode ID: {op_id}")

        arg_type = struct.unpack("<B", buf.read(1))[0]
        arg = None

        if arg_type == ARG_NONE:
            arg = None
        elif arg_type == ARG_INT:
            arg = struct.unpack("<q", buf.read(8))[0]
        elif arg_type == ARG_STR:
            s_len = struct.unpack("<I", buf.read(4))[0]
            arg = buf.read(s_len).decode('utf-8')
        elif arg_type == ARG_TUPLE_STR_INT:
            s_len, int_val = struct.unpack("<II", buf.read(8))
            s_str = buf.read(s_len).decode('utf-8')
            arg = (s_str, int_val)
        else:
            raise SerializationError(f"Unknown instruction argument tag: {arg_type}")

        line_no = struct.unpack("<I", buf.read(4))[0]
        line = line_no if line_no != 0 else None
        return Instruction(op, arg, line)

    def deserialize_file(self, data: bytes) -> Chunk:
        """Validates CHUD magic header, version, and CRC32 checksum before deserializing."""
        if len(data) < 10:
            raise SerializationError("File is too short to be a valid .chudc binary.")

        magic, version, expected_crc = struct.unpack("<4sHI", data[:10])
        if magic != MAGIC_BYTES:
            raise SerializationError(f"Invalid magic header: expected {MAGIC_BYTES}, got {magic}")
        if version != FORMAT_VERSION:
            raise SerializationError(f"Unsupported bytecode version {version} (current is {FORMAT_VERSION})")

        payload = data[10:]
        actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise SerializationError(f"CRC32 Checksum mismatch: binary file is corrupted ({actual_crc:#x} != {expected_crc:#x})")

        return self.deserialize_chunk(payload)


# ── High-Level Convenience API ──

def serialize_chunk(chunk: Chunk) -> bytes:
    """Serializes a Chunk into a complete .chudc binary file payload."""
    return BytecodeSerializer().serialize_file(chunk)


def deserialize_chunk(binary_data: bytes) -> Chunk:
    """Deserializes a complete .chudc binary file payload into a Chunk."""
    return BytecodeDeserializer().deserialize_file(binary_data)


def compile_source_to_chudc(source_code: str, output_path: str):
    """Compiles CHUD source string directly to a .chudc binary file."""
    chunk = compile_source(source_code)
    bin_data = serialize_chunk(chunk)
    with open(output_path, "wb") as f:
        f.write(bin_data)
    return output_path


def load_chudc_file(filepath: str) -> Chunk:
    """Reads a .chudc binary file from disk and returns the executable Chunk."""
    with open(filepath, "rb") as f:
        data = f.read()
    return deserialize_chunk(data)

--[[
Edit this file in order to enable models for statically-linked functions.
Models drastically reduce path explosion at the expense of more complex expressions.

Suppose that the binary you want to analyze contains at address 0x1234 a function
that computes a standard CRC32 checksum. To enable the model for the CRC32 function,
add the following lines:

g_function_models["{{ target }}"] = {}
g_function_models["{{ target }}"][0x1234] = {
    xor_result=true, --Must be true for standard CRC32
    type="crc32"
}

Function models assume specific calling conventions and function arguments.
They may not work with different variations of the implementation of the
original function. For example, the CRC32 model only supports one type of
CRC32 algorithm and only functions that have the following signature:

    uint32 crc32(uint8_t *buf, unsigned size)

Please refer to StaticFunctionModels.cpp file for details on their implementation.
]]--

g_function_models["{{ target }}"] = {}

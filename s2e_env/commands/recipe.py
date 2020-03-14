"""
Copyright (c) 2018 Cyberhaven

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import binascii
import logging
import struct

from pwn import asm

from s2e_env.command import ProjectCommand


logger = logging.getLogger('recipe')

REGISTERS = {
    'i386': ['eax', 'ecx', 'edx', 'ebx', 'esp', 'ebp', 'esi', 'edi'],
    'amd64': ['rax', 'rcx', 'rdx', 'rbx', 'rsp', 'rbp', 'rsi', 'rdi']
}

BITS = {
    'i386': 32,
    'amd64': 64
}

PCREG = {
    'i386': 'EIP',
    'amd64': 'RIP'
}


def expand_byte(b, size):
    s = '%x' % b
    return int(s * size, 16)


def gen_marker(size_in_bytes):
    """
    Returns a pattern of the given size.
    We need a marker with distinct bytes to avoid overlaps
    with instructions that begin with the same byte as the marker.
    """
    marker = ''
    for i in range(0, size_in_bytes):
        marker = '%s%02x' % (marker, i+1)
    return int(marker, 16)


def write_stripped_string(fp, string, line_prefix=''):
    for line in string.splitlines():
        stripped = line.strip()
        if stripped:
            fp.write('%s%s\n' % (line_prefix, stripped))


def assemble_raw(inst_list, arch, convert_to_hex):
    # pylint doesn't see the arch argument
    # pylint: disable=unexpected-keyword-arg
    assembled = asm('\n'.join(inst_list), arch=arch)
    ret = [bytes([val]) for i, val in enumerate(assembled)]
    if convert_to_hex:
        for i, val in enumerate(ret):
            ret[i] = '0x%s' % binascii.hexlify(val).decode()
    return ret


SIZE_TO_STRUCT = [None, '<B', '<H', None, '<L', None, None, None, '<Q']


def resolve_marker(asmd, marker, marker_size, var_name):
    pk = struct.pack(SIZE_TO_STRUCT[marker_size], marker)
    pk_idx = b''.join(asmd).find(pk)
    if pk_idx == -1:
        raise Exception('Could not find marker %s in %s' % (marker, asmd))

    for i, val in enumerate(asmd):
        asmd[i] = '0x%s' % binascii.hexlify(val).decode()

    if marker_size == 1:
        asmd[pk_idx] = '%s' % var_name
    else:
        for i in range(0, marker_size):
            asmd[pk_idx + i] = '%s[%d]' % (var_name, i)


def assemble(instructions, markers, arch):
    asmd_instr = []
    acc_instr = []
    for instr in instructions.splitlines():
        found_marker = None
        found_varname = None
        for marker, var_name in markers.items():
            if instr.find(marker) != -1:
                found_marker = marker
                found_varname = var_name
                break

        if found_marker is not None:
            asmd_instr += assemble_raw(acc_instr, arch, True)
            acc_instr = []

            # AAAA or BBBB means 2 bytes, CCCCCCCC 4 bytes, etc.
            marker_size = len(found_marker) // 2
            value = gen_marker(marker_size)
            new_instr = instr.replace(found_marker, str(value))
            asmd = assemble_raw([new_instr], arch, False)
            resolve_marker(asmd, value, marker_size, found_varname)
            asmd_instr += asmd
        else:
            acc_instr.append(instr)

    asmd_instr += assemble_raw(acc_instr, arch, True)
    return asmd_instr


def type1(fp, arch, platform, gp_reg_index):
    size = BITS[arch] // 8
    reg_pc_mask = expand_byte(0xff, size)

    gp_reg_str = REGISTERS[arch][gp_reg_index].upper()

    header = """
    # Assume both PC and GP are symbolic
    :type=1
    :arch={2}
    :platform={3}
    :gp={0}
    :reg_mask=0x{1:x}
    :pc_mask=0x{1:x}
    """.format(gp_reg_str, reg_pc_mask, arch, platform)

    write_stripped_string(fp, header)

    for i in range(0, BITS[arch] // 8):
        fp.write('{1}[{0}] == $pc[{0}]\n'.format(i, PCREG[arch]))

    for i in range(0, BITS[arch] // 8):
        fp.write('{0}[{1}] == $gp[{1}]\n'.format(gp_reg_str, i))


def type1_shellcode(fp, arch, platform, gp_reg_index):
    pc_reg_index = 0
    if gp_reg_index == pc_reg_index:
        pc_reg_index += 1

    size = BITS[arch] // 8
    gp_marker = 'XX' * size
    pc_marker = 'YY' * size
    reg_pc_mask = expand_byte(0xff, size)

    instr = \
    """
    mov {0}, {2}
    mov {1}, {3}
    jmp {1}
    """.format(REGISTERS[arch][gp_reg_index], REGISTERS[arch][pc_reg_index],
               gp_marker, pc_marker)

    markers = {gp_marker: '$gp', pc_marker: '$pc'}
    assembled = assemble(instr, markers, arch)

    fp.write('# Set GP and EIP with shellcode\n')

    instr = instr.replace(gp_marker, '$gp')
    instr = instr.replace(pc_marker, '$pc')

    write_stripped_string(fp, instr, '# ')

    header = \
    """ \
    :reg_mask=0x{1:x}
    :pc_mask=0x{1:x}
    :type=1
    :arch={2}
    :platform={3}
    :gp={0}
    :exec_mem={4}
    """.format(REGISTERS[arch][gp_reg_index].upper(), reg_pc_mask, arch, platform, PCREG[arch])

    write_stripped_string(fp, header)

    for i, val in enumerate(assembled):
        fp.write('[{2}+{0}] == {1}\n'.format(i, val, PCREG[arch]))


def type2_decree_shellcode_i386_0(fp):
    addr_var = 'XXXX'
    size_var1 = 'YY'
    size_var2 = 'ZZ'

    instr = \
    """
    xor eax,eax
    xor ebx,ebx
    xor edx,edx
    mov al,0x2
    mov bl,0x1
    mov ecx,0x43470000
    or  ecx,{0}
    mov dh, {1}
    mov dl, {2}
    xor esi, esi
    int 0x80
    """.format(addr_var, size_var1, size_var2)

    markers = {addr_var: '$addr', size_var1: '$size[0]', size_var2: '$size[1]'}
    assembled = assemble(instr, markers, 'i386')

    fp.write('# Shellcode recipe for T2 PoV\n')
    write_stripped_string(fp, instr, '# ')

    header = \
    """
    :type=2
    :arch=i386
    :platform=decree
    :skip=0
    :exec_mem=EIP
    """

    write_stripped_string(fp, header)

    for i, val in enumerate(assembled):
        fp.write('[EIP+{0}] == {1}\n'.format(i, val))


def type2_decree_shellcode_i386_1(fp):
    instr = \
    """
    xor eax,eax
    xor ebx,ebx
    xor edx,edx
    mov al,0x2
    mov bl,0x1
    mov cx,0x32d4
    xor cx,0x7193
    shl ecx,0x8
    mov cl,0xc0
    shl ecx,0x8
    mov dh,0x10
    xor esi,esi
    int 0x80
    """

    assembled = assemble(instr, {}, 'i386')

    fp.write('# Shellcode recipe for T2 PoV\n')
    write_stripped_string(fp, instr, '# ')

    header = \
    """
    :type=2
    :arch=i386
    :platform=decree
    :skip=0
    :exec_mem=EIP
    """
    write_stripped_string(fp, header)
    for i, val in enumerate(assembled):
        fp.write('[EIP+{0}] == {1}\n'.format(i, val))


class Command(ProjectCommand):
    """
    Generate recipes for PoV generation.
    """

    help = 'Generate recipes for PoV generation'

    # pylint: disable=too-many-arguments
    def get_recipe_path(self, recipe_type, arch, platform, name, gp_reg):
        filename = 'type%d_%s_%s_%s' % (recipe_type, arch, platform, name)
        if gp_reg is not None:
            filename = '%s_%s' % (filename, REGISTERS[arch][gp_reg])
        filename = '%s.rcp' % filename
        return self.project_path('recipes', filename)

    def handle(self, *args, **options):
        logging.getLogger('pwnlib').setLevel('ERROR')

        img_os_desc = self.image['os']

        archs = []
        if img_os_desc['arch'] == 'x86_64':
            archs.append('amd64')
            archs.append('i386')
        elif img_os_desc['arch'] == 'i386':
            archs.append('i386')

        type1_handlers = [('reg', type1), ('shellcode', type1_shellcode)]

        for arch in archs:
            for gp_reg in range(0, len(REGISTERS[arch])):
                platform = 'generic'

                for flavor, handler in type1_handlers:
                    path = self.get_recipe_path(1, arch, platform, flavor, gp_reg)
                    with open(path, 'w') as fp:
                        logger.info('Writing recipe to %s', path)
                        handler(fp, arch, platform, gp_reg)

        # Specific for decree
        if 'decree' in img_os_desc['binary_formats']:
            type2_handlers = [(0, type2_decree_shellcode_i386_0), (1, type2_decree_shellcode_i386_1)]

            for i, handler in type2_handlers:
                path = self.get_recipe_path(2, 'i386', 'decree', 'shellcode_%d' % i, None)

                with open(path, 'w') as fp:
                    logger.info('Writing recipe to %s', path)
                    handler(fp)

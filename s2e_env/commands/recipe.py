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
    s = f'{b:x}'
    return int(s * size, 16)


def gen_marker(size_in_bytes):
    """
    Returns a pattern of the given size.
    We need a marker with distinct bytes to avoid overlaps
    with instructions that begin with the same byte as the marker.
    """
    marker = ''
    for i in range(0, size_in_bytes):
        marker = f'{marker}{i+1:02x}'
    return int(marker, 16)


def write_stripped_string(fp, string, line_prefix=''):
    for line in string.splitlines():
        stripped = line.strip()
        if stripped:
            fp.write(f'{line_prefix}{stripped}\n')


def assemble_raw(inst_list, arch, convert_to_hex):
    # pylint doesn't see the arch argument
    # pylint: disable=unexpected-keyword-arg
    assembled = asm('\n'.join(inst_list), arch=arch)
    ret = [bytes([val]) for i, val in enumerate(assembled)]
    if convert_to_hex:
        for i, val in enumerate(ret):
            ret[i] = f'0x{binascii.hexlify(val).decode()}'
    return ret


SIZE_TO_STRUCT = [None, '<B', '<H', None, '<L', None, None, None, '<Q']


def resolve_marker(asmd, marker, marker_size, var_name):
    pk = struct.pack(SIZE_TO_STRUCT[marker_size], marker)
    pk_idx = b''.join(asmd).find(pk)
    if pk_idx == -1:
        raise Exception(f'Could not find marker {marker} in {asmd}')

    for i, val in enumerate(asmd):
        asmd[i] = f'0x{binascii.hexlify(val).decode()}'

    if marker_size == 1:
        asmd[pk_idx] = f'{var_name}'
    else:
        for i in range(0, marker_size):
            asmd[pk_idx + i] = f'{var_name}[{i}]'


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

    header = f"""
    # Assume both PC and GP are symbolic
    :type=1
    :arch={arch}
    :platform={platform}
    :gp={gp_reg_str}
    :reg_mask=0x{reg_pc_mask:x}
    :pc_mask=0x{reg_pc_mask:x}
    """

    write_stripped_string(fp, header)

    for i in range(0, BITS[arch] // 8):
        fp.write(f'{PCREG[arch]}[{i}] == $pc[{i}]\n')

    for i in range(0, BITS[arch] // 8):
        fp.write(f'{gp_reg_str}[{i}] == $gp[{i}]\n')


def type1_shellcode(fp, arch, platform, gp_reg_index):
    pc_reg_index = 0
    if gp_reg_index == pc_reg_index:
        pc_reg_index += 1

    size = BITS[arch] // 8
    gp_marker = 'XX' * size
    pc_marker = 'YY' * size
    reg_pc_mask = expand_byte(0xff, size)

    instr = \
        f"""
        mov {REGISTERS[arch][gp_reg_index]}, {gp_marker}
        mov {REGISTERS[arch][pc_reg_index]}, {pc_marker}
        jmp {REGISTERS[arch][pc_reg_index]}
        """

    markers = {gp_marker: '$gp', pc_marker: '$pc'}
    assembled = assemble(instr, markers, arch)

    fp.write('# Set GP and EIP with shellcode\n')

    instr = instr.replace(gp_marker, '$gp')
    instr = instr.replace(pc_marker, '$pc')

    write_stripped_string(fp, instr, '# ')

    header = \
        f""" \
        :reg_mask=0x{reg_pc_mask:x}
        :pc_mask=0x{reg_pc_mask:x}
        :type=1
        :arch={arch}
        :platform={platform}
        :gp={REGISTERS[arch][gp_reg_index].upper()}
        :exec_mem={PCREG[arch]}
        """

    write_stripped_string(fp, header)

    for i, val in enumerate(assembled):
        fp.write(f'[{PCREG[arch]}+{i}] == {val}\n')


def type2_decree_shellcode_i386_0(fp):
    addr_var = 'XXXX'
    size_var1 = 'YY'
    size_var2 = 'ZZ'

    instr = \
        f"""
        xor eax,eax
        xor ebx,ebx
        xor edx,edx
        mov al,0x2
        mov bl,0x1
        mov ecx,0x43470000
        or  ecx,{addr_var}
        mov dh, {size_var1}
        mov dl, {size_var2}
        xor esi, esi
        int 0x80
        """

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
        fp.write(f'[EIP+{i}] == {val}\n')


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
        fp.write(f'[EIP+{i}] == {val}\n')


class Command(ProjectCommand):
    """
    Generate recipes for PoV generation.
    """

    help = 'Generate recipes for PoV generation'

    # pylint: disable=too-many-arguments
    def get_recipe_path(self, recipe_type, arch, platform, name, gp_reg):
        filename = f'type{recipe_type}_{arch}_{platform}_{name}'
        if gp_reg is not None:
            filename = f'{filename}_{REGISTERS[arch][gp_reg]}'
        filename = f'{filename}.rcp'
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
                    with open(path, 'w', encoding='utf-8') as fp:
                        logger.info('Writing recipe to %s', path)
                        handler(fp, arch, platform, gp_reg)

        # Specific for decree
        if 'decree' in img_os_desc['binary_formats']:
            type2_handlers = [(0, type2_decree_shellcode_i386_0), (1, type2_decree_shellcode_i386_1)]

            for i, handler in type2_handlers:
                path = self.get_recipe_path(2, 'i386', 'decree', f'shellcode_{i}', None)

                with open(path, 'w', encoding='utf-8') as fp:
                    logger.info('Writing recipe to %s', path)
                    handler(fp)

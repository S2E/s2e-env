// THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF
// ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO
// THE IMPLIED WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A
// PARTICULAR PURPOSE.
//
// Copyright (c) Microsoft Corporation. All rights reserved

// From
// https://docs.microsoft.com/en-us/windows/desktop/dlls/creating-a-simple-dynamic-link-library
//
// Install `mingw-w64`
// Compile with `x86_64-w64-mingw32-gcc myputs.c -o myputs.dll -shared`

// The myPuts function writes a null-terminated string to
// the standard output device.

// The export mechanism used here is the __declspec(export)
// method supported by Microsoft Visual Studio, but any
// other export method supported by your development
// environment may be substituted.

#include <windows.h>

#define EOF (-1)

#ifdef __cplusplus
extern "C" {
#endif

__declspec(dllexport) INT __cdecl MyPuts(LPWSTR Msg) {
    DWORD Written;
    HANDLE Conout;
    BOOL Ret;

    // Get a handle to the console output device.

    Conout = CreateFileW(L"CONOUT$", GENERIC_WRITE, FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);

    if (Conout == INVALID_HANDLE_VALUE) {
        return EOF;
    }

    // Write a null-terminated string to the console output device.

    while (*Msg != L'\0') {
        Ret = WriteConsole(Conout, Msg, 1, &Written, NULL);
        if ((Ret == FALSE) || (Written != 1)) {
            return EOF;
        }

        Msg++;
    }

    return 0;
}

#ifdef __cplusplus
}
#endif

#pragma once
#include <windows.h>

// Original forwarding pointers must be visible before either hook is published.
inline bool InstallOwnedPair(void** table, void* connect, void* disconnect,
                             void** original_connect, void** original_disconnect) {
    DWORD previous{};
    if (!VirtualProtect(table, 2 * sizeof(void*), PAGE_READWRITE, &previous)) return false;
    *original_connect = table[0];
    *original_disconnect = table[1];
    MemoryBarrier();
    InterlockedExchangePointer(reinterpret_cast<void* volatile*>(&table[0]), connect);
    InterlockedExchangePointer(reinterpret_cast<void* volatile*>(&table[1]), disconnect);
    DWORD ignored{};
    return VirtualProtect(table, 2 * sizeof(void*), previous, &ignored) != FALSE;
}

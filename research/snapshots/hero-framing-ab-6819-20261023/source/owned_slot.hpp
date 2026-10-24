#pragma once
#include <windows.h>
#include <cstdint>

// Compare-and-swap only the reviewed pointer. Restore original page protection
// and never replace a later hook installed by somebody else.
struct OwnedSlot {
    void** cell{}; void* before{}; void* after{}; bool installed=false;
    static bool readable(void** location) {
        MEMORY_BASIC_INFORMATION info{};
        return location && VirtualQuery(location,&info,sizeof(info))==sizeof(info)
            && info.State==MEM_COMMIT && !(info.Protect&(PAGE_NOACCESS|PAGE_GUARD))
            && reinterpret_cast<std::uintptr_t>(location)+sizeof(void*)<=reinterpret_cast<std::uintptr_t>(info.BaseAddress)+info.RegionSize;
    }
    bool install(void** location,void* expected,void* replacement) {
        if(!readable(location)) return false;
        if(installed) return cell==location && *cell==after;
        if(!location || !expected || !replacement || *location!=expected) return false;
        DWORD prior{};
        if(!VirtualProtect(location,sizeof(void*),PAGE_READWRITE,&prior)) return false;
        cell=location; before=expected; after=replacement;
        MemoryBarrier();
        installed=InterlockedCompareExchangePointer(reinterpret_cast<void* volatile*>(cell),after,before)==before;
        DWORD ignored{};
        const bool protection_ok=VirtualProtect(location,sizeof(void*),prior,&ignored)!=FALSE;
        return installed && protection_ok;
    }
    bool restore() {
        if(!installed) return true;
        if(!readable(cell)) { installed=false;return false; }
        if(*cell!=after) { installed=false; return false; }
        DWORD prior{};
        if(!VirtualProtect(cell,sizeof(void*),PAGE_READWRITE,&prior)) return false;
        const bool exchanged=InterlockedCompareExchangePointer(reinterpret_cast<void* volatile*>(cell),before,after)==after;
        DWORD ignored{};
        const bool protection_ok=VirtualProtect(cell,sizeof(void*),prior,&ignored)!=FALSE;
        if(exchanged) installed=false;
        return exchanged && protection_ok;
    }
};

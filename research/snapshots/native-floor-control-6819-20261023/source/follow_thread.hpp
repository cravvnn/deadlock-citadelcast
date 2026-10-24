#pragma once
#include <windows.h>
#include <atomic>
#include <mutex>

namespace follow {
// Foreign/audio/worker readers must remain native and must not wait for the
// main camera-update lock: that update may itself be waiting for those workers.
template<class Native,class Filtered>
auto ReadOnOwner(std::atomic<DWORD>& owner,std::recursive_mutex& mutex,Native native,Filtered filtered) {
    auto result=native();
    const DWORD thread=GetCurrentThreadId();
    if(owner.load(std::memory_order_acquire)!=thread)return result;
    std::lock_guard lock(mutex);
    if(owner.load(std::memory_order_acquire)==thread)filtered(result);
    return result;
}
}

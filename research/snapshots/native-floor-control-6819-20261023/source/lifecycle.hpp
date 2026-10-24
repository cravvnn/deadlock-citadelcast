#pragma once
#include <atomic>

// Own one registration phase. Failed underlying Connect never registers;
// Disconnect claims cleanup once before forwarding to the real implementation.
class OwnedRegistration {
    std::atomic<bool> ready_{false};
public:
    template<class Register> bool connect(bool underlying_ok, Register&& registration) {
        if (!underlying_ok) return false;
        if (ready_.load(std::memory_order_acquire)) return true;
        registration();
        ready_.store(true, std::memory_order_release);
        return true;
    }
    template<class Cleanup, class Forward> void disconnect(Cleanup&& cleanup, Forward&& forward) {
        if (ready_.exchange(false, std::memory_order_acq_rel)) cleanup();
        forward();
    }
};

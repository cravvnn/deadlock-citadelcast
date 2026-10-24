#include "follow_output.hpp"
#include "follow_thread.hpp"
#include "playback.hpp"
#include <cassert>
#include <cstdio>
#include <future>

int main(){
    follow::Filter filter;follow::FramePermit permit;follow::Pose pose{};
    walker::Playback playback;walker::Gates gates;
    assert(playback.arm(0,gates,12));
    assert(playback.step(3,gates).action==walker::Action::Begin);
    assert(filter.begin(3,pose) && playback.begin_ready(3));
    unsigned full_checks=0,copies=0;
    auto check=[&]{++full_checks;return gates.valid();};
    auto render=[&](double now,unsigned channel){
        float native[3]={77,88,99};
        const bool wrote=permit.copy(filter,native,channel,true,now);
        if(wrote)++copies;else assert(native[0]==77 && native[1]==88 && native[2]==99);
        return wrote;
    };
    // Reproduce the first live boundary: many position/angle reads after begin,
    // before any advanced sample. They must stay native and call no full gates.
    for(unsigned n=0;n<635;++n)assert(!render(3.001,n<451?0:3));
    assert(full_checks==0 && copies==0);
    double now=3;
    for(unsigned frame=0;frame<720;++frame){
        now+=1.0/60;
        permit.invalidate();
        assert(!render(now,0));
        assert(playback.step(now,gates).action==walker::Action::Apply);
        {
            follow::FramePermit::NativeUpdate manager(permit);
            {
                follow::FramePermit::NativeUpdate camera(permit);
                assert(!render(now,0));
            }
            pose[0]+=1;
            assert(permit.refresh(now,check));
            assert(filter.advance(now,pose,true));
            // Native slot4/other manager math must also get raw outputs even
            // after slot3 published a checked sample.
            assert(!render(now,0));
        }
        for(unsigned n=0;n<635;++n)assert(render(now,n<451?0:3));
        assert(full_checks==frame+1);
    }
    assert(copies==720*635);
    assert(!render(now+.251,0) && !render(now-.001,0));
    gates.input_idle=false;permit.invalidate();
    assert(!permit.refresh(now+.01,check));
    assert(!render(now+.01,0));
    assert(playback.step(now+.01,gates).action==walker::Action::Cancel);
    filter.stop("gate changed");permit.invalidate();
    assert(!render(now+.01,0));
    gates.input_idle=true;
    assert(!permit.refresh(NAN,check));
    assert(!permit.allows(NAN) && !permit.allows(INFINITY));
    // A genuinely slow frame still cancels; the time bound is unchanged.
    walker::Playback slow;assert(slow.arm(0,gates));
    assert(slow.step(3,gates).action==walker::Action::Begin && slow.begin_ready(3));
    assert(slow.step(3.812,gates).action==walker::Action::Cancel);
    std::atomic<DWORD> owner{GetCurrentThreadId()};std::recursive_mutex mutex;
    {
        std::lock_guard main_lock(mutex);
        auto foreign=std::async(std::launch::async,[&]{
            return follow::ReadOnOwner(owner,mutex,[]{return 77;},[](int&){assert(false);});
        });
        assert(foreign.wait_for(std::chrono::milliseconds(500))==std::future_status::ready);
        assert(foreign.get()==77);
    }
    std::puts("follow_output: 635 reads/frame, no per-getter full gates, raw native update, fresh-only output, stop and unchanged 812ms gap rejection passed");
}

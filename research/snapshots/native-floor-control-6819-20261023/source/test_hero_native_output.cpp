#include "hero_data_output.hpp"
#include "phase_timing.hpp"
#include "follow_thread.hpp"
#include <cassert>
#include <cstdio>
#include <future>

namespace {
using Camera=std::array<float,32>;
std::array<float,7> Read(const Camera& camera){
    std::array<float,7> result{};std::memcpy(result.data(),camera.data()+8,sizeof(result));return result;
}
bool Publish(Camera& camera,const hero::Rig& rig,float lens,bool owned){
    return hero::WriteNativePose(camera.data()+8,rig.pose(),lens,owned && rig.active());
}
void SamePose(const Camera& camera,const hero::Rig& rig,float lens){
    const auto result=Read(camera);
    for(unsigned n=0;n<6;++n)assert(result[n]==static_cast<float>(rig.pose()[n]));
    assert(result[6]==lens);
    for(unsigned n=0;n<camera.size();++n)if(n<8||n>=15)assert(camera[n]==-777);
}
}
int main(int argc,char** argv){
    assert(argc==2);
    hero::Rig rig;hero::Vec root{100,200,300};constexpr float lens=73.25f;
    assert(rig.begin(0,root,12));
    Camera owned;owned.fill(-777);Camera original;original.fill(888);const auto original_before=original;
    // Factory/load may leave scaffold coordinates in a new owned object. Prime
    // it before selection, so the first ordinary native getter sees the rig.
    for(unsigned n=8;n<15;++n)owned[n]=9999;
    assert(Publish(owned,rig,lens,true));SamePose(owned,rig,lens);
    const auto first_visible=Read(owned);assert(first_visible[0]!=9999);
    double now=0;
    for(unsigned frame=0;frame<300;++frame){
        now+=1.0/60;root[0]+=2;root[1]+=.5;
        if(frame==100)root[0]+=350;
        assert(rig.advance(now,root,true));
        // Native slot3 supplies its curve; the same-owner override is applied
        // before post-update/render reads. Original observer fields stay native.
        for(unsigned n=8;n<15;++n)owned[n]=9000;
        assert(Publish(owned,rig,lens,true));SamePose(owned,rig,lens);
        assert(original==original_before);
    }
    // Normal native readers on any thread see the same selected camera fields;
    // there is no owner-thread-only alternative pose or lock to acquire here.
    const auto main_view=Read(owned);
    std::atomic<DWORD> legacy_owner{GetCurrentThreadId()};std::recursive_mutex legacy_mutex;
    auto legacy_native=[&]{std::array<float,7> value{};value.fill(888);value[6]=lens;return value;};
    const auto legacy_main=follow::ReadOnOwner(legacy_owner,legacy_mutex,legacy_native,[&](auto& result){
        assert(rig.copy(result.data(),0,true) && rig.copy(result.data()+3,3,true));
    });
    auto legacy_worker=std::async(std::launch::async,[&]{
        return follow::ReadOnOwner(legacy_owner,legacy_mutex,legacy_native,[](auto&){assert(false);});
    });
    assert(legacy_main!=legacy_worker.get()); // Actual old helper reproduces split viewpoints.
    auto worker=std::async(std::launch::async,[&]{return Read(owned);});
    assert(worker.get()==main_view);
    const auto before=owned;
    assert(!Publish(owned,rig,lens,false) && owned==before);
    auto bad=rig.pose();bad[2]=NAN;
    assert(!hero::WriteNativePose(owned.data()+8,bad,lens,true) && owned==before);
    assert(!hero::WriteNativePose(owned.data()+8,rig.pose(),NAN,true) && owned==before);
    assert(!hero::WriteNativePose(owned.data()+8,rig.pose(),0,true) && owned==before);
    assert(!hero::WriteNativePose(nullptr,rig.pose(),lens,true));
    rig.stop("operator stop");assert(!Publish(owned,rig,lens,true) && owned==before);
    hero::Rig discontinuity;assert(discontinuity.begin(0,root,0));
    auto jumped=root;jumped[0]+=513;
    assert(!discontinuity.advance(.01,jumped,true) && !Publish(owned,discontinuity,lens,true) && owned==before);
    hero::Rig slow;assert(slow.begin(0,root,0));
    assert(!slow.advance(.251,root,true) && !Publish(owned,slow,lens,true) && owned==before);
    hero::PhaseCosts costs;
    costs.gates.add(1,1.002);costs.gates.add(2,2.004);
    costs.compose.add(NAN,2);costs.compose.add(3,2);
    assert(costs.gates.count==2 && costs.compose.count==0);
    FILE* output{};assert(fopen_s(&output,argv[1],"wb")==0 && output);
    costs.write(output);std::fclose(output);
    std::puts("hero_native_output: prime-before-select and post-native/pre-reader pose, shared native reader view, entry lens preservation, original observer untouched and ownership/stop/invalid/gap/jump refusals passed");
    std::puts("hero_native_output: old owner-filter helper reproduces split viewpoints; owned camera ordinary readers agree");
}

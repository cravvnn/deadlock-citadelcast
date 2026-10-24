#include "take_trace.hpp"
#include <cassert>
#include <cstring>
#include <limits>
#include <string>

int main(int argc,char** argv) {
    const auto invalid=walker_trace::Classify(0x100,0x200,0x200,0x300,0x400);
    assert(std::strcmp(invalid.module,"other")==0 && invalid.rva==0);
    assert(walker_trace::Classify(0x210,0x200,0x200,0x300,0x400).rva==0x10);
    assert(std::strcmp(walker_trace::Classify(0x310,0x300,0x200,0x300,0x400).module,"engine")==0);
    assert(walker_trace::Classify(0x510,0x500,0x200,0x300,0x400).rva==0);
    const auto self=reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    auto exit=walker_trace::Capture("owned test","no game",0,0,self);
    assert(exit.present && exit.count>0 && exit.count<=walker_trace::kFrames);
    bool own_frame=false;
    for(unsigned n=0;n<exit.count;++n) {
        if(std::strcmp(exit.frames[n].module,"adapter")==0) own_frame=true;
        else assert(exit.frames[n].rva==0);
    }
    assert(own_frame);
    walker_trace::Sample sample;sample.present=true;
    sample.elapsed=0.75;sample.native_start=10;sample.native_now=10.75f;
    sample.pose[0]=std::numeric_limits<float>::quiet_NaN();
    sample.pose[1]=std::numeric_limits<float>::infinity();
    // Deliberately corrupt the count to prove serialized frames stay bounded.
    exit.count=walker_trace::kFrames+100;
    assert(argc==2);
    FILE* out{};assert(fopen_s(&out,argv[1],"wb")==0 && out);
    std::fputs("{\"kind\":\"owning test\"",out);walker_trace::Write(out,sample,exit);
    std::fputs("}\n",out);std::fclose(out);
    // Resetting the take clears all prior samples and stack metadata.
    sample={};exit={};
    assert(!sample.present && !exit.present && exit.count==0);
    std::puts("take_trace: owned OS unwind, relative modules, unknown-address omission, bounded serialization, nonfinite JSON and reset passed");
}

#include "playback.hpp"
#include <cassert>
#include <fstream>
#include <iostream>
#include <limits>

int main(int argc,char** argv) {
    assert(argc==2);
    std::ifstream input(argv[1]); assert(input.good());
    double t,max_error=0; std::size_t rows=0;
    while(input>>t) {
        const auto actual=walker::Evaluate(t);
        for(unsigned c=0;c<walker::Count;++c) {
            double expected; assert(bool(input>>expected));
            const double error=std::abs(actual[c]-expected);
            max_error=std::max(max_error,error);
            assert(error<2e-9);
            assert(static_cast<float>(actual[c])==static_cast<float>(expected));
        }
        ++rows;
    }
    assert(rows==4135);
    const auto first=walker::Evaluate(0),last=walker::Evaluate(walker::kDuration);
    assert(first==walker::Evaluate(-100) && last==walker::Evaluate(100));
    assert(std::abs(first[walker::Pitch]+19.8)<1e-10);
    assert(std::abs(last[walker::Roll]+0.422219999745721)<1e-10);
    assert(std::abs(first[walker::Aspect]-1.7777777910232544)<1e-12);
    assert(std::abs(last[walker::Aspect]-1.4400000107288362)<1e-12);
    assert(std::abs(std::tan(walker::VerticalFov(first)*3.14159265358979323846/360)-first[walker::Lens])<1e-12);
    assert(std::abs(std::tan(walker::HorizontalFov(last)*3.14159265358979323846/360)-last[walker::Lens]*last[walker::Aspect])<1e-12);
    using namespace walker;
    Playback p; Gates g;
    assert(p.arm(100,g)); assert(!p.arm(100,g));
    assert(p.step(102.999,g).action==Action::None);
    assert(p.step(103,g).action==Action::Begin);
    double previous=0;
    for(unsigned i=1;i<=14125;++i) {
        const auto tick=p.step(103+i/1000.0,g);
        assert(tick.action==Action::Apply);
        assert(tick.time>=previous); previous=tick.time;
    }
    assert(p.phase()==Phase::Endpoint);
    assert(previous==14.125);
    assert(p.step(117.126,g).action==Action::Complete);
    assert(p.step(117.127,g).action==Action::None);
    // Every independent gate cancels before another pose can be supplied.
    for(unsigned gate=0;gate<5;++gate) {
        Playback q; assert(q.arm(0,g)); assert(q.step(3,g).action==Action::Begin);
        Gates changed=g;
        if(gate==0) changed.identity=false;
        if(gate==1) changed.foreground=false;
        if(gate==2) changed.viewer=false;
        if(gate==3) changed.input_idle=false;
        if(gate==4) changed.camera=false;
        assert(q.step(3.01,changed).action==Action::Cancel);
        assert(q.step(3.02,g).action==Action::None);
    }
    assert(p.arm(200,g)); assert(p.step(199,g).action==Action::Cancel);
    assert(p.arm(200,g)); assert(p.step(std::numeric_limits<double>::quiet_NaN(),g).action==Action::Cancel);
    assert(p.arm(200,g)); assert(p.step(205,g).action==Action::Cancel);
    assert(p.arm(200,g)); assert(p.step(203,g).action==Action::Begin);
    assert(p.step(204,g).action==Action::Cancel);
    // Camera-file loading is preparation, not part of the authored shot time.
    assert(p.arm(300,g)); assert(p.step(303,g).action==Action::Begin);
    assert(p.begin_ready(303.2));
    assert(p.step(303.3,g).time>0.099999 && p.step(303.3,g).time<0.100001);
    assert(MayRestoreAspect(1.44f,1.44f,true));
    assert(!MayRestoreAspect(1.6f,1.44f,true));
    assert(!MayRestoreAspect(1.44f,1.44f,false));
    std::cout<<"golden_samples="<<rows<<" max_double_error="<<max_error
             <<" duration="<<kDuration<<"; cancellation/timing/restore gates passed\n";
}

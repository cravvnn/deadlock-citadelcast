#include "shot_library.hpp"
#include "playback.hpp"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>

int main(int argc,char** argv) {
    assert(argc==2);
    assert(!walker::FindShot(nullptr) && !walker::FindShot("../escape") && !walker::FindShot("unknown"));
    std::ifstream input(argv[1]);assert(input.good());
    std::string line,id;unsigned count=0;double largest=0;
    while(std::getline(input,line)) {
        std::istringstream row(line);double time;row>>id>>time;
        const auto* shot=walker::FindShot(id.c_str());assert(shot);
        const auto pose=walker::EvaluateShot(*shot,time);
        for(unsigned n=0;n<walker::Count;++n) {
            double expected;row>>expected;assert(!row.fail());
            assert(std::isfinite(pose[n]));largest=std::max(largest,std::abs(pose[n]-expected));
            assert(std::abs(pose[n]-expected)<1e-8);
            assert(static_cast<float>(pose[n])==static_cast<float>(expected));
        }
        ++count;
    }
    assert(count>4100);
    const auto* reverse=walker::FindShot("walker-reverse");
    assert(walker::EvaluateShot(*reverse,0)==walker::Evaluate(14.125));
    assert(walker::EvaluateShot(*reverse,14.125)==walker::Evaluate(0));
    const auto* short_shot=walker::FindShot("arrival");
    walker::Playback playback;walker::Gates gates;
    assert(!playback.arm(0,gates,0) && !playback.arm(0,gates,NAN));
    assert(playback.arm(0,gates,short_shot->duration));
    assert(playback.step(3,gates).action==walker::Action::Begin);
    assert(playback.begin_ready(3));
    for(double time=3.1;time<3+short_shot->duration;time+=0.1)
        assert(playback.step(time,gates).action==walker::Action::Apply);
    assert(playback.step(3+short_shot->duration,gates).action==walker::Action::Apply);
    assert(playback.step(3+short_shot->duration+0.01,gates).action==walker::Action::Complete);
    // A long library entry cannot silently change the short take's duration.
    assert(playback.duration()==short_shot->duration);
    std::printf("shot_library_samples=%u max_error=%.9g; original/reverse/windows/endpoints, unknown selection and per-take clock passed\n",count,largest);
}

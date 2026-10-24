#include "hero_composition.hpp"
#include "follow_output.hpp"
#include <cassert>
#include <cstdio>

double aim_error(const follow::Pose& pose,const hero::Vec& root){
    const auto focus=hero::Focus(root);hero::Vec delta{};
    for(unsigned n=0;n<3;++n)delta[n]=focus[n]-pose[n];
    const double radians=3.14159265358979323846/180,p=pose[3]*radians,y=pose[4]*radians;
    const hero::Vec forward={std::cos(p)*std::cos(y),std::cos(p)*std::sin(y),-std::sin(p)};
    double dot=0;for(unsigned n=0;n<3;++n)dot+=forward[n]*delta[n]/hero::Length(delta);
    return std::acos(std::clamp(dot,-1.0,1.0))/radians;
}
int main(){
    // Exact failure class: smoothing a moving camera and its old direction
    // independently can leave its hero far from the optical axis.
    follow::Filter previous;follow::Pose start={-260,0,48,0,0,0},next={-260,200,48,0,0,0};
    assert(previous.begin(0,start) && previous.advance(1.0/60,next,true));
    assert(aim_error(previous.pose(),{0,200,0})>30);
    for(unsigned rate:{30,60,144}){
        hero::Rig rig;hero::Vec root{};assert(rig.begin(0,root,0));
        for(unsigned frame=1;frame<=rate*4;++frame){
            const double now=double(frame)/rate;
            root={100*std::sin(now),100*std::cos(now),20*std::sin(now)};
            if(frame>=rate)root[1]+=350; // Dash while holding initial bearing.
            assert(rig.advance(now,root,true));
            assert(aim_error(rig.pose(),root)<2e-6 && rig.lag()<=128.000001);
        }
        assert(rig.recenters()>0);
        follow::FramePermit permit;assert(permit.refresh(4,[]{return true;}));
        float pos[3]{},angles[3]{};
        assert(permit.copy(rig,pos,0,true,4) && permit.copy(rig,angles,3,true,4));
        follow::Pose emitted={pos[0],pos[1],pos[2],angles[0],angles[1],angles[2]};
        assert(aim_error(emitted,root)<1e-4);
        rig.stop("operator stop");const float unchanged=pos[0];
        assert(!permit.copy(rig,pos,0,true,4) && pos[0]==unchanged);
    }
    for(unsigned fault=0;fault<5;++fault){
        hero::Rig rig;hero::Vec root{};assert(rig.begin(1,root,45));
        double now=1.01;bool allowed=true;
        if(fault==0)now=1.251;
        if(fault==1)now=.99;
        if(fault==2)root[0]=513;
        if(fault==3)root[2]=NAN;
        if(fault==4)allowed=false;
        assert(!rig.advance(now,root,allowed) && !rig.active());
        float untouched[3]={7,8,9};assert(!rig.copy(untouched,0,true) && untouched[0]==7);
    }
    std::puts("hero_composition: independently delayed aim reproduces framing drift; current-anchor aim stays centered through350unit dash/height changes at30/60/144Hz, bounded128unit lag, finite float output and stop gates passed");
}

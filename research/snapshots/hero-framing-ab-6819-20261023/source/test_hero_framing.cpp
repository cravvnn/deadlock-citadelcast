#include "hero_entry.hpp"
#include <cassert>
#include <cstdio>
using hero::HeadingPolicy;
bool close(double a,double b,double tolerance=1e-8){return std::abs(a-b)<tolerance;}
int main(){
    const hero::Vec root={100,200,300};
    // Different native viewing directions must converge to the same actual
    // hero-front composition. Legacy native-heading anchoring fails this case.
    for(auto policy:{HeadingPolicy::HeroStart,HeadingPolicy::HeroFollow}){
        hero::EntryRig a,b;
        assert(a.begin(0,root,{100,0,384,0,90,0},policy,30));
        assert(b.begin(0,root,{300,200,384,0,180,0},policy,30));
        for(unsigned n=1;n<=240;++n){assert(a.advance(n/120.0,root,true,30));assert(b.advance(n/120.0,root,true,30));}
        for(unsigned n=0;n<6;++n)assert(close(a.pose()[n],b.pose()[n])|| (n>=3&&close(follow::Wrap(a.pose()[n]-b.pose()[n]),0)));
        assert(close(a.bearing(),75));
        assert(close(a.pose()[0],100+260*std::cos(75*3.14159265358979323846/180)));
    }
    hero::Rig turning,held;
    assert(turning.begin(0,root,200,HeadingPolicy::HeroFollow,355));
    assert(held.begin(0,root,200,HeadingPolicy::HeroStart,355));
    double old=turning.bearing();
    for(unsigned n=1;n<=600;++n){
        const double t=n/120.0,yaw=n<240?5:185;
        // Strafe sideways: framing follows facing, never movement direction.
        const hero::Vec moving={100+t*30,200-t*20,300};
        assert(turning.advance(t,moving,true,yaw)&&held.advance(t,moving,true,yaw));
        const double delta=turning.bearing()-old;
        assert(std::abs(delta)<=90/120.0+1e-9);
        if(n<240)assert(delta>=0&&turning.bearing()<=410); // 355->5 takes +10, not -350
        assert(held.bearing()==400);old=turning.bearing();
        assert(turning.lag()<=128&&held.lag()<=128);
    }
    assert(std::abs(follow::Wrap(turning.bearing()-(185+45)))<1);
    const auto before=turning.pose();assert(!turning.advance(5.01,root,true,NAN)&&turning.pose()==before);
    hero::Rig bad;assert(!bad.begin(0,root,0,HeadingPolicy::HeroStart,NAN));
    for(auto p:{HeadingPolicy::HeroStart,HeadingPolicy::HeroFollow}){
        hero::Rig gate,gap,jump;assert(gate.begin(0,root,0,p,0)&&gap.begin(0,root,0,p,0)&&jump.begin(0,root,0,p,0));
        assert(!gate.advance(.01,root,false,0)&&!gap.advance(.26,root,true,0)&&!jump.advance(.01,{1000,200,300},true,0));
    }
    // Default entry point is the preserved legacy contract.
    hero::Rig legacy;assert(legacy.begin(0,root,90)&&legacy.bearing()==135);
    std::puts("hero_framing: same hero-facing start independent of chase heading, bounded shortest-angle following, held bearing, strafe, invalid facing and unchanged cancellation passed");
}

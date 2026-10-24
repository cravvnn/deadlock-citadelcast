// Pure accepted rig headers + synthetic poses. No Windows/game/API bindings.
#include "hero_composition.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>

int main(int argc,char** argv){
    if(argc!=2){std::cerr<<"Expected one lab output filename\n";return 2;}
    std::ofstream out(argv[1],std::ios::trunc);
    if(!out)return 3;
    hero::Rig a,b;
    const hero::Vec origin{0,0,0};
    if(!a.begin(0,origin,0,hero::HeadingPolicy::HeroFollow,0) ||
       !b.begin(0,origin,0,hero::HeadingPolicy::HeroStart,0))return 4;
    out<<std::setprecision(12)<<"{\"kind\":\"synthetic matched input through accepted A/B rig headers\","
       <<"\"game_access\":false,\"duration\":8,\"entry_included\":false,\"frames\":[\n";
    double previous_bearing=a.bearing();
    for(int i=0;i<=960;++i){
        const double t=i/120.0;
        const hero::Vec root{40*t,50*std::sin(t*.5),0};
        const double yaw=std::clamp((t-1)*30.0,0.0,180.0);
        if(i && (!a.advance(t,root,true,yaw) || !b.advance(t,root,true,yaw)))return 5;
        if(std::abs(b.bearing()-45)>1e-9 ||
            (i && std::abs(a.bearing()-previous_bearing)>90.0/120+1e-8))return 6;
        previous_bearing=a.bearing();
        auto vector=[&](const auto& p){out<<'['<<p[0]<<','<<p[1]<<','<<p[2]<<']';};
        if(i)out<<",\n";
        out<<"{\"t\":"<<t<<",\"yaw\":"<<yaw<<",\"focus\":";vector(a.focus());
        out<<",\"a_camera\":";vector(a.pose());out<<",\"b_camera\":";vector(b.pose());
        out<<",\"a_desired_bearing\":"<<a.bearing()<<",\"b_desired_bearing\":"<<b.bearing()<<'}';
    }
    out<<"]}\n";
    if(!out || a.bearing()-b.bearing()<150)return 7;
    std::cout<<"961 matched synthetic samples; fixed B bearing and A rate limit checked; no game access\n";
    return 0;
}

#include "hero_entry.hpp"
#include "hero_data_output.hpp"
#include <cassert>
#include <cstdio>
constexpr double pi=3.14159265358979323846,rad=pi/180;
follow::Pose native_pose(const hero::Vec& root,double heading){
    const auto focus=hero::Focus(root);
    return {focus[0]-260*std::cos(heading*rad),focus[1]-260*std::sin(heading*rad),focus[2]+36,std::atan2(36.0,260.0)/rad,heading,0};
}
double centering_error(const follow::Pose& pose,const hero::Vec& root){
    const auto focus=hero::Focus(root);hero::Vec delta{};
    for(unsigned n=0;n<3;++n)delta[n]=focus[n]-pose[n];
    const hero::Vec f={std::cos(pose[3]*rad)*std::cos(pose[4]*rad),std::cos(pose[3]*rad)*std::sin(pose[4]*rad),-std::sin(pose[3]*rad)};
    double dot=0;for(unsigned n=0;n<3;++n)dot+=f[n]*delta[n]/hero::Length(delta);
    return std::acos(std::clamp(dot,-1.0,1.0))/rad;
}
int main(){
    hero::Vec root{};const auto entry=native_pose(root,0);
    hero::Rig hard_cut;assert(hard_cut.begin(0,root,entry[4]));
    assert(follow::Distance(entry,hard_cut.pose())>400&&std::abs(follow::Wrap(entry[4]-hard_cut.pose()[4]))>100);
    for(unsigned rate:{30,60,144})for(double heading:{-179.0,0.0,179.0,359.0,719.0}){
        root={};const auto native=native_pose(root,heading);hero::EntryRig rig;hero::Rig steady;
        assert(rig.begin(0,root,native)&&steady.begin(0,root,native[4]));
        // First published owned-camera pose must be exactly the existing native
        // chase view, before any transition sample or camera selection.
        assert(rig.pose()==native);std::array<float,7> owned;owned.fill(-777);
        assert(hero::WriteNativePose(owned.data(),rig.pose(),83.25f,rig.active()));
        for(unsigned n=0;n<6;++n)assert(owned[n]==static_cast<float>(native[n]));assert(owned[6]==83.25f);
        auto previous=rig.pose();
        for(unsigned frame=1;frame<=rate*3;++frame){
            const double now=double(frame)/rate;
            root={80*now,20*std::sin(now),5*std::sin(now)};
            if(now>=1.5)root[0]+=350; // Original dash behavior after entry.
            assert(rig.advance(now,root,true)&&steady.advance(now,root,true));
            assert(centering_error(rig.pose(),root)<2e-6&&rig.lag()<=128.000001);
            const double radius=std::hypot(rig.pose()[0]-rig.focus()[0],rig.pose()[1]-rig.focus()[1]);assert(radius>=64);
            if(now<=1){
                assert(follow::Distance(rig.pose(),previous)<55.0*30/rate);
                for(unsigned n=3;n<6;++n)assert(std::abs(rig.pose()[n]-previous[n])<12.0*30/rate);
            }else{
                // Beyond entry, positions and physical view direction are the
                // unchanged steady rig, including dash/lag-envelope response.
                for(unsigned n=0;n<3;++n)assert(std::abs(rig.pose()[n]-steady.pose()[n])<1e-8);
                for(unsigned n=3;n<6;++n)assert(std::abs(follow::Wrap(rig.pose()[n]-steady.pose()[n]))<1e-8);
            }
            previous=rig.pose();
        }
        assert(rig.entry_complete()&&rig.min_radius()>=64&&rig.entry_elapsed()==1);
        assert(rig.max_position_step()<55.0*30/rate&&rig.max_angle_step()<12.0*30/rate);
    }
    // Preserve measured native framing residual and bank at entry, then center
    // continuously from the actual moving camera instead of smoothing old aim.
    hero::EntryRig residual;root={};auto native=entry;native[3]+=3;native[4]+=5;native[5]=12;
    assert(residual.begin(0,root,native)&&residual.pose()==native);
    for(unsigned n=1;n<=120;++n){root[1]+=.5;assert(residual.advance(n/120.0,root,true));}
    assert(centering_error(residual.pose(),root)<2e-6&&std::abs(residual.pose()[5])<1e-8);
    for(unsigned fault=0;fault<5;++fault){
        hero::EntryRig rig;root={};assert(rig.begin(1,root,entry));const auto before=rig.pose();
        double now=1.01;bool allowed=true;
        if(fault==0)now=1.251;if(fault==1)now=.99;if(fault==2)root[0]=513;if(fault==3)root[2]=NAN;if(fault==4)allowed=false;
        assert(!rig.advance(now,root,allowed)&&!rig.active()&&rig.pose()==before);
        float output[3]={7,8,9};assert(!rig.copy(output,0,true)&&output[0]==7);
        std::array<float,7> owned;owned.fill(77);assert(!hero::WriteNativePose(owned.data(),rig.pose(),90,rig.active())&&owned[0]==77);
    }
    hero::EntryRig invalid;auto pole=entry;pole[0]=pole[1]=0;
    assert(!invalid.begin(0,{},pole)&&!invalid.active());auto distant=entry;distant[0]=-2049;
    assert(!invalid.begin(0,{},distant)&&!invalid.active());
    std::puts("hero_entry: old hard cut exceeds400units/100degrees; exact native first publication, centered non-crossing1second orbit at30/60/144Hz, yaw-wrap continuity, unchanged steady/dash rig and gap/identity/stop/no-publication bounds passed");
}

#pragma once
#include <cstdint>
#include <limits>
namespace hero {
// No I/O here. Stop marks a completed take only AFTER camera restoration;
// Status supplies an exclusive-create writer. Failed saves block another take.
class TakeArchive {
    std::uint64_t id_=0;
    bool active_=false,pending_=false;
public:
    std::uint64_t id()const{return id_;}
    bool pending()const{return pending_;}
    bool arm(){
        if(active_||pending_||id_==(std::numeric_limits<std::uint64_t>::max)())return false;
        ++id_;active_=true;return true;
    }
    void finish(){if(active_){active_=false;pending_=true;}}
    template<class Write>bool publish(Write write){
        if(!pending_)return true;
        if(!write(id_))return false;
        pending_=false;return true;
    }
};
}

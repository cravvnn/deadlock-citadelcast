#pragma once
#include <cstdint>

namespace hero {
// Absolute origin is a lazily rebuilt engine cache. Resolve a coherent target,
// let its reviewed native getter refresh that cache, then read it afresh.
// No target sample is published after lost ownership, identity or cancellation.
class FreshTargetSampler {
    bool busy_=false;
    const char* reason_="idle";
    bool refuse(const char* reason){reason_=reason;++refused;return false;}
public:
    std::uint64_t refreshes=0,samples=0,refused=0;
    const char* reason()const{return reason_;}
    void reset(){*this=FreshTargetSampler{};}
    template<class Target,class Allowed,class Read,class Refresh>
    bool sample(const Target& initial,Target& output,Allowed allowed,Read read,Refresh refresh){
        if(busy_||!allowed())return refuse("hero fresh target gate/reentry refused");
        busy_=true;
        struct Exit{bool& busy;~Exit(){busy=false;}}exit{busy_};
        Target before{};
        if(!read(before)||!before.same_identity(initial))return refuse("hero target changed before native getter");
        if(!allowed())return refuse("hero native getter gate changed");
        if(!refresh(before))return refuse("hero native absolute origin getter refused");
        ++refreshes;
        if(!allowed())return refuse("hero target gate changed after native getter");
        Target after{};
        if(!read(after)||!after.same_identity(initial)||!after.same_identity(before))
            return refuse("hero target changed after native getter");
        if(!allowed())return refuse("hero fresh target final gate changed");
        output=after;++samples;reason_="ready after native absolute origin getter";return true;
    }
};
}

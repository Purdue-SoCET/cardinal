#include <optional>
#include <string>
#include <utility>

template <typename T> // basically auto (any struct)
class ForwardingIF {
public:
    explicit ForwardingIF(std::string name_set) // initializer list, names the FWIF
        : name_internal(std::move(name_set)) {} 

    void push(T payload_in) { // into fwif
        payload_out = std::move(payload_in);
    }

    std::optional<T> pop() { // out to next stage. destructive read
        auto out = std::move(payload_out);
        payload_out.reset();
        return out;
    }

    void set_wait(bool wait_set = true) { //stall
        wait_internal = wait_set;
    }

private:
    std::string name_internal;
    bool wait_internal = false;
    std::optional<T> payload_out;
};

template <typename T>
class LatchIF {
public:
    explicit LatchIF(std::string name_set) // initializer list, names the LatchIF
        : name_internal(std::move(name_set)) {}

    bool ready_for_push() const { //cycle/stage complete, prevents overwrite
        return !payload_out.has_value();
    }

    bool push(T payload_in) {
        if (!ready_for_push()) //?
            return false;

        payload_out = std::move(payload_in);
        return true;
    }

    void force_push(T payload_in) { 
        payload_out = std::move(payload_in);
    }

    std::optional<T> pop() {
        auto out = std::move(payload_out);
        payload_out.reset();
        return out;
    }

private:
    std::string name_internal;
    std::optional<T> payload_out;
};
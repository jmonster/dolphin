# Also usable alone: configure this directory to test the additions without
# building the unrelated emulator. The normal ENABLE_TESTS build includes it.
cmake_minimum_required(VERSION 3.25)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  project(DolphinSwitch2KitTests LANGUAGES NONE)
  enable_testing()
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)
get_filename_component(DOLPHIN_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)

function(add_switch2kit_test name script)
  add_test(NAME Switch2Kit.${name}
    COMMAND "${Python3_EXECUTABLE}" "${DOLPHIN_ROOT}/Tools/${script}" ${ARGN})
  set_tests_properties(Switch2Kit.${name} PROPERTIES TIMEOUT 20 LABELS Switch2Kit)
endfunction()

add_switch2kit_test(ChangeSelection test_switch2kit_ci.py)
add_switch2kit_test(NativeExecution test_native_ci_execution.py)
add_switch2kit_test(Integration test_switch2kit.py)
add_switch2kit_test(AutoConnect test_switch2kit_autoconnect.py)
add_switch2kit_test(Mapping test_switch2kit_mapping.py --sanitize)
add_switch2kit_test(Host test_switch2kit_host.py --sanitize)
find_program(SWITCH2KIT_CLANGXX clang++ REQUIRED)
add_switch2kit_test(CapacityClang test_switch2kit_capacity.py)
set_tests_properties(Switch2Kit.CapacityClang PROPERTIES ENVIRONMENT "CXX=${SWITCH2KIT_CLANGXX}")
if(CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux")
  find_program(SWITCH2KIT_GXX g++ REQUIRED)
  add_switch2kit_test(CapacityGCC test_switch2kit_capacity.py)
  set_tests_properties(Switch2Kit.CapacityGCC PROPERTIES ENVIRONMENT "CXX=${SWITCH2KIT_GXX}")
  add_switch2kit_test(Runtime test_switch2kit_runtime.py)
endif()

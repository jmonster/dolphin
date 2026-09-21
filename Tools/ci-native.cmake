# CI-only build acceleration, loaded through CMAKE_PROJECT_dolphin-emu_INCLUDE.
# Keep upstream source/build defaults and the complete native build graph intact.
if(NOT "$ENV{GITHUB_ACTIONS}" STREQUAL "true")
  message(FATAL_ERROR "Tools/ci-native.cmake is only for GitHub Actions builds")
endif()

# project() has now loaded upstream FlagsOverride.cmake. Command-line -D flags
# alone are shadowed by that file's normal variables on MSVC.
if(NOT "$ENV{GITHUB_EVENT_NAME}" STREQUAL "workflow_dispatch")
  if(MSVC)
    set(CMAKE_C_FLAGS_RELEASE "/Od /Ob0 /DNDEBUG /Z7")
    set(CMAKE_CXX_FLAGS_RELEASE "/Od /Ob0 /DNDEBUG /Z7")
  elseif(APPLE)
    set(CMAKE_C_FLAGS_RELEASE "-O0 -DNDEBUG")
    set(CMAKE_CXX_FLAGS_RELEASE "-O0 -DNDEBUG")
  endif()
endif()
message(STATUS "Native CI C Release flags: ${CMAKE_C_FLAGS_RELEASE}")
message(STATUS "Native CI C++ Release flags: ${CMAKE_CXX_FLAGS_RELEASE}")

# Windows already shares upstream's PCH. On POSIX, compile the same upstream
# header once per target instead of parsing it for every translation unit.
# Per-target PCHs preserve each target's own defines, include paths and flags.
# Do not use unity builds (which change translation-unit boundaries), touch the
# production sources, replace libraries, or exclude a source from compilation.
function(switch2kit_ci_precompile_headers)
  if(MSVC)
    return()
  endif()
  foreach(target common audiocommon inputcommon videocommon discio core dolphin-emu)
    if(TARGET ${target})
      target_precompile_headers(${target} PRIVATE
        "$<$<COMPILE_LANGUAGE:CXX>:${PROJECT_SOURCE_DIR}/Source/PCH/pch.h>")
    endif()
  endforeach()
  if(TARGET dolphin-emu AND ENABLE_QT)
    target_precompile_headers(dolphin-emu PRIVATE
      "$<$<COMPILE_LANGUAGE:CXX>:<QtWidgets$<ANGLE-R>>")
  endif()
endfunction()
cmake_language(DEFER CALL switch2kit_ci_precompile_headers)

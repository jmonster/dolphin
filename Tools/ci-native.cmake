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
      # Upstream gives some files different flags (e.g. ARM crypto ISA flags).
      # They still compile normally; a target-wide PCH cannot represent those
      # per-source options. Resolve properties in the target's source directory.
      get_target_property(source_dir ${target} SOURCE_DIR)
      get_target_property(sources ${target} SOURCES)
      foreach(source IN LISTS sources)
        if(source MATCHES "\\$<")
          continue()
        endif()
        if(NOT IS_ABSOLUTE "${source}")
          set(source "${source_dir}/${source}")
        endif()
        foreach(property COMPILE_FLAGS COMPILE_OPTIONS COMPILE_DEFINITIONS)
          get_source_file_property(value "${source}" DIRECTORY "${source_dir}" ${property})
          if(value)
            set_source_files_properties("${source}" DIRECTORY "${source_dir}"
              PROPERTIES SKIP_PRECOMPILE_HEADERS ON)
          endif()
        endforeach()
      endforeach()
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

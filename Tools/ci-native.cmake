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
    # Child project() calls can load the upstream override again. Directory
    # options follow configuration flags, so the actual child compiler commands
    # must also end in /Od /Ob0. Keep CRT selection, defines and warnings intact.
    add_compile_options(
      "$<$<AND:$<CONFIG:Release>,$<COMPILE_LANGUAGE:C,CXX>>:/Od>"
      "$<$<AND:$<CONFIG:Release>,$<COMPILE_LANGUAGE:C,CXX>>:/Ob0>"
    )
  elseif(APPLE)
    set(CMAKE_C_FLAGS_RELEASE "-O0 -DNDEBUG")
    set(CMAKE_CXX_FLAGS_RELEASE "-O0 -DNDEBUG")
  endif()
endif()
message(STATUS "Native CI C Release flags: ${CMAKE_C_FLAGS_RELEASE}")
message(STATUS "Native CI C++ Release flags: ${CMAKE_CXX_FLAGS_RELEASE}")

# Configure probes compile once and almost never hit the object cache. Do not
# route hundreds of feature checks through another compiler-wrapper process.
# Restore launchers on actual build targets after configuration, below.
set(_switch2kit_c_launcher "${CMAKE_C_COMPILER_LAUNCHER}")
set(_switch2kit_cxx_launcher "${CMAKE_CXX_COMPILER_LAUNCHER}")
set(CMAKE_C_COMPILER_LAUNCHER "")
set(CMAKE_CXX_COMPILER_LAUNCHER "")

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

function(switch2kit_ci_cache_targets directory)
  get_property(children DIRECTORY "${directory}" PROPERTY SUBDIRECTORIES)
  foreach(child IN LISTS children)
    switch2kit_ci_cache_targets("${child}")
  endforeach()
  get_property(targets DIRECTORY "${directory}" PROPERTY BUILDSYSTEM_TARGETS)
  foreach(target IN LISTS targets)
    get_target_property(kind ${target} TYPE)
    if(kind MATCHES "^(EXECUTABLE|STATIC_LIBRARY|SHARED_LIBRARY|MODULE_LIBRARY|OBJECT_LIBRARY)$")
      get_target_property(pch ${target} PRECOMPILE_HEADERS)
      get_target_property(reuse_pch ${target} PRECOMPILE_HEADERS_REUSE_FROM)
      # Native PCH consumption must not be turned back into expensive per-file
      # preprocessing. Other targets retain the bounded compiler-object cache.
      if(NOT pch AND NOT reuse_pch)
        set_target_properties(${target} PROPERTIES
          C_COMPILER_LAUNCHER "${_switch2kit_c_launcher}"
          CXX_COMPILER_LAUNCHER "${_switch2kit_cxx_launcher}")
      endif()
    endif()
  endforeach()
endfunction()
cmake_language(DEFER CALL switch2kit_ci_precompile_headers)
cmake_language(DEFER CALL switch2kit_ci_cache_targets "${PROJECT_SOURCE_DIR}")

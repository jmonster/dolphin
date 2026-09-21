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
    # Child project() calls and target options can override configuration flags.
    # Apply the final Release options to completed targets below, not here.
  elseif(APPLE)
    set(CMAKE_C_FLAGS_RELEASE "-O0 -DNDEBUG")
    set(CMAKE_CXX_FLAGS_RELEASE "-O0 -DNDEBUG")
  elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    # Keep the complete upstream Linux suite optimized. Explicit artifacts keep
    # the upstream Release optimizer; automatic qualification uses -O1.
    set(CMAKE_C_FLAGS_RELEASE "-O1 -DNDEBUG")
    set(CMAKE_CXX_FLAGS_RELEASE "-O1 -DNDEBUG")
  endif()
endif()
message(STATUS "Native CI C Release flags: ${CMAKE_C_FLAGS_RELEASE}")
message(STATUS "Native CI C++ Release flags: ${CMAKE_CXX_FLAGS_RELEASE}")

# Keep all configure probes as real compilations AND links. On Windows, use
# the runner's native LLVM linker for automatic smoke builds, including probes;
# MSVC still compiles every C/C++ source and owns Dolphin's shared PCH.
if(CMAKE_HOST_WIN32 AND MSVC AND NOT "$ENV{GITHUB_EVENT_NAME}" STREQUAL "workflow_dispatch")
  if(CMAKE_VERSION VERSION_LESS 3.29)
    message(FATAL_ERROR "Native Windows CI requires CMake 3.29 or newer for LLD")
  endif()
  find_program(CMAKE_LINKER_LLD NAMES lld-link HINTS "$ENV{ProgramFiles}/LLVM/bin" REQUIRED)
  set(CMAKE_C_USING_LINKER_LLD "${CMAKE_LINKER_LLD}")
  set(CMAKE_CXX_USING_LINKER_LLD "${CMAKE_LINKER_LLD}")
  list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES CMAKE_LINKER_LLD)
  set(CMAKE_LINKER_TYPE LLD)
  # Test the same runtime configuration as the real application, not a separate
  # Debug link with an incremental PDB/manifest cycle for every tiny probe.
  set(CMAKE_TRY_COMPILE_CONFIGURATION Release)
  message(STATUS "Native CI Windows linker: ${CMAKE_LINKER_LLD}")
endif()

# Use a CI-specific variable, not CMAKE_*_COMPILER_LAUNCHER in the job's
# environment: those standard variables also reach every nested SDK/fixture
# configuration and try_compile project. Clearing a normal variable alone does
# not clear that environment or its cache entry. Keep actual feature/link probes.
set(_switch2kit_c_launcher "${CMAKE_C_COMPILER_LAUNCHER}")
set(_switch2kit_cxx_launcher "${CMAKE_CXX_COMPILER_LAUNCHER}")
if(DEFINED ENV{S2K_CI_COMPILER_CACHE})
  if(NOT _switch2kit_c_launcher)
    set(_switch2kit_c_launcher "$ENV{S2K_CI_COMPILER_CACHE}")
  endif()
  if(NOT _switch2kit_cxx_launcher)
    set(_switch2kit_cxx_launcher "$ENV{S2K_CI_COMPILER_CACHE}")
  endif()
endif()
foreach(language C CXX)
  set(CMAKE_${language}_COMPILER_LAUNCHER "" CACHE STRING "Native CI target-only cache" FORCE)
  set(CMAKE_${language}_COMPILER_LAUNCHER "")
  unset(ENV{CMAKE_${language}_COMPILER_LAUNCHER})
endforeach()

# Windows already shares upstream's PCH. On POSIX, compile the same upstream
# header once per target instead of parsing it for every translation unit.
# Per-target PCHs preserve each target's own defines, include paths and flags.
# Do not use unity builds (which change translation-unit boundaries), touch the
# production sources, replace libraries, or exclude a source from compilation.
# Upstream splits its unit suite into object libraries. Accelerate their C++
# parsing too, rather than only the two sources in the final tests executable.
function(switch2kit_ci_test_targets directory output)
  get_property(targets DIRECTORY "${directory}" PROPERTY BUILDSYSTEM_TARGETS)
  get_property(children DIRECTORY "${directory}" PROPERTY SUBDIRECTORIES)
  foreach(child IN LISTS children)
    switch2kit_ci_test_targets("${child}" child_targets)
    list(APPEND targets ${child_targets})
  endforeach()
  set(${output} "${targets}" PARENT_SCOPE)
endfunction()

function(switch2kit_ci_precompile_headers)
  # The pinned shader compiler supplies its own PCH for these exact sources.
  # Its parser headers dominated cold compilation; compile that same upstream
  # header once, without unity builds or changing the shader compiler's sources.
  if(TARGET glslang)
    get_target_property(glslang_source glslang SOURCE_DIR)
    target_precompile_headers(glslang PRIVATE "${glslang_source}/MachineIndependent/pch.h")
  endif()
  if(MSVC)
    return()
  endif()
  set(pch_targets common audiocommon inputcommon videocommon discio core uicommon
                  videoogl videonull videosoftware videometal videovulkan
                  dolphin-tool dolphin-emu)
  if(TARGET tests)
    get_target_property(test_dir tests SOURCE_DIR)
    switch2kit_ci_test_targets("${test_dir}" test_targets)
    list(APPEND pch_targets ${test_targets})
  endif()
  foreach(target IN LISTS pch_targets)
    if(TARGET ${target})
      get_target_property(kind ${target} TYPE)
      if(NOT kind MATCHES "^(EXECUTABLE|STATIC_LIBRARY|SHARED_LIBRARY|MODULE_LIBRARY|OBJECT_LIBRARY)$")
        continue()
      endif()
      get_target_property(existing_pch ${target} PRECOMPILE_HEADERS)
      get_target_property(reuse_pch ${target} PRECOMPILE_HEADERS_REUSE_FROM)
      if(existing_pch OR reuse_pch)
        continue()
      endif()
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
      get_target_property(links ${target} LINK_LIBRARIES)
      # Source/PCH implements MSVC's /Yc and /Yu manually, through build_pch
      # and the use_pch interface. PRECOMPILE_HEADERS does not describe it.
      set(manual_pch FALSE)
      if(MSVC AND (target STREQUAL "build_pch" OR "use_pch" IN_LIST links))
        set(manual_pch TRUE)
      endif()
      if(pch OR reuse_pch OR manual_pch)
        # Explicitly clear inherited launchers as well. Merely doing nothing
        # left SDL and child-project PCH consumers going through sccache.
        set_target_properties(${target} PROPERTIES
          C_COMPILER_LAUNCHER "" CXX_COMPILER_LAUNCHER "")
      else()
        set_target_properties(${target} PROPERTIES
          C_COMPILER_LAUNCHER "${_switch2kit_c_launcher}"
          CXX_COMPILER_LAUNCHER "${_switch2kit_cxx_launcher}")
      endif()
      if(NOT "$ENV{GITHUB_EVENT_NAME}" STREQUAL "workflow_dispatch")
        # Let CMake remove only unnecessary compile-order edges between static
        # and object libraries. It retains explicit add_dependencies(), generated
        # source prerequisites, custom-command side effects and final link inputs.
        # Never clear MANUALLY_ADDED_DEPENDENCIES or edit Ninja's generated graph.
        if(kind MATCHES "^(STATIC_LIBRARY|OBJECT_LIBRARY)$")
          set_property(TARGET ${target} PROPERTY OPTIMIZE_DEPENDENCIES ON)
        endif()
        if(MSVC)
          # SHELL keeps this final pair together even when an inherited /Od or
          # /Ob0 appeared earlier: CMake otherwise de-duplicates the last copy.
          # Apply to the PCH producer and consumers alike; keep Debug, CRT,
          # warning, architecture, debug-information and sanitizer flags intact.
          target_compile_options(${target} PRIVATE
            "$<$<AND:$<CONFIG:Release>,$<COMPILE_LANGUAGE:C,CXX>>:SHELL:/Od /Ob0>")
        endif()
      endif()
      if(NOT MSVC AND NOT "$ENV{GITHUB_EVENT_NAME}" STREQUAL "workflow_dispatch")
        # Upstream appends -ggdb even in Release. Keep line-level backtraces,
        # without emitting full type debug information for every smoke object.
        # Append after upstream initialization; never change sanitizer options.
        target_compile_options(${target} PRIVATE
          "$<$<AND:$<CONFIG:Release>,$<COMPILE_LANGUAGE:C,CXX>>:-g1>")
      endif()
    endif()
  endforeach()
endfunction()
cmake_language(DEFER CALL switch2kit_ci_precompile_headers)
cmake_language(DEFER CALL switch2kit_ci_cache_targets "${PROJECT_SOURCE_DIR}")

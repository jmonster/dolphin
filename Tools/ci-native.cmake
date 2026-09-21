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
    # Preserve the setup hook's child-directory options. The deferred target
    # pass below is authoritative when later target options would override them.
    add_compile_options(
      "$<$<AND:$<CONFIG:Release>,$<COMPILE_LANGUAGE:C,CXX>>:/Od>"
      "$<$<AND:$<CONFIG:Release>,$<COMPILE_LANGUAGE:C,CXX>>:/Ob0>"
    )
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
  # Upstream appends /DEBUG to every executable link, including feature probes.
  # Tiny configure executables still compile and link, but need neither a PDB
  # nor an application manifest. These check-only options never reach targets.
  list(APPEND CMAKE_REQUIRED_LINK_OPTIONS /DEBUG:NONE /MANIFEST:NO)
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
  if(TARGET dolphin-emu AND ENABLE_QT AND
     NOT "$ENV{GITHUB_EVENT_NAME}" STREQUAL "workflow_dispatch")
    # moc reads the Qt target's sources; it need not wait for every linked
    # library to finish compiling. Preserve explicit generated/staging targets
    # and any existing autogen dependencies. CMake still owns source generation
    # and the application's compile/link dependency graph.
    get_target_property(qt_dependencies dolphin-emu MANUALLY_ADDED_DEPENDENCIES)
    if(qt_dependencies)
      set_property(TARGET dolphin-emu APPEND PROPERTY AUTOGEN_TARGET_DEPENDS
        ${qt_dependencies})
    endif()
    # This upstream generated header is a core source, not a Qt source. Keep
    # the file prerequisite without waiting for core's compiled static library.
    if(TARGET core)
      get_target_property(core_binary core BINARY_DIR)
      get_target_property(core_sources core SOURCES)
      if("AchievementApprovedHash.h" IN_LIST core_sources)
        set_property(TARGET dolphin-emu APPEND PROPERTY AUTOGEN_TARGET_DEPENDS
          "${core_binary}/AchievementApprovedHash.h")
      endif()
    endif()
    set_property(TARGET dolphin-emu PROPERTY AUTOGEN_ORIGIN_DEPENDS OFF)
  endif()
  if(MSVC)
    # DolphinQt enables RTTI and does not use the core's shared /GR- PCH.
    # Give it its own PCH, with its actual Qt flags, as on POSIX. Do not mix
    # CMake's PCH with an existing manual or target-provided implementation.
    if(TARGET dolphin-emu AND ENABLE_QT)
      get_target_property(qt_links dolphin-emu LINK_LIBRARIES)
      get_target_property(qt_pch dolphin-emu PRECOMPILE_HEADERS)
      get_target_property(qt_reuse_pch dolphin-emu PRECOMPILE_HEADERS_REUSE_FROM)
      if(NOT "use_pch" IN_LIST qt_links AND NOT qt_pch AND NOT qt_reuse_pch)
        target_precompile_headers(dolphin-emu PRIVATE
          "$<$<COMPILE_LANGUAGE:CXX>:${PROJECT_SOURCE_DIR}/Source/PCH/pch.h>"
          "$<$<COMPILE_LANGUAGE:CXX>:<QtWidgets$<ANGLE-R>>")
      endif()
    endif()
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
      # Most upstream cases are one-source object libraries. Share a PCH only
      # across cases with the same target properties, directory flags and exact
      # dependency usage requirements. Reusing the tests executable would create
      # a dependency cycle: it links these cases. Use the first matching case.
      set(pch_key "")
      if(kind STREQUAL "OBJECT_LIBRARY" AND target IN_LIST test_targets)
        set(signature "")
        foreach(property COMPILE_OPTIONS COMPILE_DEFINITIONS INCLUDE_DIRECTORIES
                         LINK_LIBRARIES CXX_STANDARD CXX_STANDARD_REQUIRED CXX_EXTENSIONS
                         POSITION_INDEPENDENT_CODE CXX_VISIBILITY_PRESET
                         VISIBILITY_INLINES_HIDDEN COMPILE_FLAGS AUTOMOC AUTOUIC)
          get_target_property(value ${target} ${property})
          string(APPEND signature "|${property}=${value}")
        endforeach()
        foreach(variable CMAKE_CXX_FLAGS CMAKE_CXX_FLAGS_DEBUG CMAKE_CXX_FLAGS_RELEASE
                         CMAKE_CXX_FLAGS_RELWITHDEBINFO CMAKE_CXX_FLAGS_MINSIZEREL
                         CMAKE_INCLUDE_CURRENT_DIR CMAKE_CXX_SCAN_FOR_MODULES)
          get_directory_property(value DIRECTORY "${source_dir}" DEFINITION ${variable})
          string(APPEND signature "|${variable}=${value}")
          if(variable STREQUAL "CMAKE_INCLUDE_CURRENT_DIR" AND value)
            string(APPEND signature "|source=${source_dir}")
          endif()
        endforeach()
        # Target-context expressions may evaluate differently despite matching
        # strings. Such targets retain their own PCH instead of assuming equality.
        if(NOT signature MATCHES "TARGET_PROPERTY|TARGET_NAME|TARGET_OBJECTS")
          string(SHA256 pch_key "${signature}")
        endif()
      endif()
      if(pch_key AND DEFINED pch_provider_${pch_key})
        target_precompile_headers(${target} REUSE_FROM ${pch_provider_${pch_key}})
      else()
        target_precompile_headers(${target} PRIVATE
          "$<$<COMPILE_LANGUAGE:CXX>:${PROJECT_SOURCE_DIR}/Source/PCH/pch.h>")
        if(pch_key)
          set(pch_provider_${pch_key} ${target})
        endif()
      endif()
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
        if(APPLE)
          # Objective-C languages are enabled after the project hook. Their
          # Release flags otherwise retain -O3 even when C/C++ use -O0.
          target_compile_options(${target} PRIVATE
            "$<$<AND:$<CONFIG:Release>,$<COMPILE_LANGUAGE:C,CXX,OBJC,OBJCXX>>:-O0>"
            "$<$<AND:$<CONFIG:Release>,$<COMPILE_LANGUAGE:OBJC,OBJCXX>>:-g1>")
        endif()
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

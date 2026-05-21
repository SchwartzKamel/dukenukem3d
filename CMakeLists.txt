cmake_minimum_required(VERSION 3.16)
project(Duke3D VERSION 0.1.0 LANGUAGES C)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Find SDL2
find_package(SDL2 REQUIRED)

# Optionally find SDL2_mixer
find_package(SDL2_mixer QUIET)

# Platform defines
if(WIN32)
    add_compile_definitions(PLATFORM_WIN32 _CRT_SECURE_NO_WARNINGS)
else()
    add_compile_definitions(PLATFORM_UNIX)
endif()

add_compile_definitions(SUPERBUILD)

# Source files — keep in sync with build.mk
set(ENGINE_SRCS
    SRC/ENGINE.C
    SRC/CACHE1D.C
    SRC/MMULTI.C
)

set(GAME_SRCS
    source/GAME.C
    source/ACTORS.C
    source/GAMEDEF.C
    source/GLOBAL.C
    source/MENUES.C
    source/PLAYER.C
    source/PREMAP.C
    source/SECTOR.C
    source/SOUNDS.C
    source/RTS.C
    source/CONFIG.C
    source/ANIMLIB.C
)

set(COMPAT_SRCS
    compat/sdl_driver.c
    compat/audio_stub.c
    compat/mact_stub.c
    compat/hud.c
    compat/maxtiles_engine_value.c
    compat/maxtiles_game_value.c
    compat/maxtiles_guard.c
)

# Platform-specific socket abstraction layer (net-r15-socket-compat)
if(WIN32)
    list(APPEND COMPAT_SRCS compat/net_socket_win32.c)
else()
    list(APPEND COMPAT_SRCS compat/net_socket_posix.c)
endif()

# Force C language for uppercase .C files (GCC treats .C as C++)
set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS} PROPERTIES LANGUAGE C)

# Create executable
add_executable(duke3d ${ENGINE_SRCS} ${GAME_SRCS} ${COMPAT_SRCS})

# Enable LTO in release builds for parity with Makefile
include(CheckIPOSupported)
check_ipo_supported(RESULT _ipo_ok OUTPUT _ipo_msg)
if(_ipo_ok AND CMAKE_BUILD_TYPE STREQUAL "Release")
	set_property(TARGET duke3d PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

# Include directories
target_include_directories(duke3d PRIVATE
    ${CMAKE_SOURCE_DIR}/compat
    ${CMAKE_SOURCE_DIR}/SRC
    ${CMAKE_SOURCE_DIR}/source
)

# SDL2 includes (only needed when using old-style variables)
if(NOT TARGET SDL2::SDL2)
    target_include_directories(duke3d PRIVATE ${SDL2_INCLUDE_DIRS})
endif()

# Compiler-specific flags
if(MSVC)
    target_compile_options(duke3d PRIVATE /W0)
    # Note: LANGUAGE C property (line 54) handles .C → C compilation for MSVC.
    # Do NOT add /Tc flag here: it consumes the next token, triggering D8036 error.
else()
    # GCC/Clang: legacy code uses gnu89, compat uses gnu11
    set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
        PROPERTIES COMPILE_FLAGS "-std=gnu89 -w -x c")
    set_source_files_properties(${COMPAT_SRCS}
        PROPERTIES COMPILE_FLAGS "-std=gnu11 -Wall")
    # Fast math for engine rendering (fixed-point safe)
    # Append -ffast-math to the base flags set above to avoid override
    set_source_files_properties(SRC/ENGINE.C
        PROPERTIES APPEND_STRING COMPILE_FLAGS " -ffast-math")
    # Strip symbols in release builds (Unix/Linux)
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        target_link_options(duke3d PRIVATE -s)
    endif()
endif()

# ENGINE.C needs the ENGINE define
set_source_files_properties(SRC/ENGINE.C PROPERTIES COMPILE_DEFINITIONS ENGINE)

# Link libraries — prefer modern imported targets (SDL2 2.24+)
if(TARGET SDL2::SDL2)
    target_link_libraries(duke3d PRIVATE SDL2::SDL2)
    if(TARGET SDL2::SDL2main)
        target_link_libraries(duke3d PRIVATE SDL2::SDL2main)
    endif()
else()
    target_link_libraries(duke3d PRIVATE ${SDL2_LIBRARIES})
endif()

if(SDL2_mixer_FOUND)
    target_compile_definitions(duke3d PRIVATE HAVE_SDL2_MIXER)
    target_link_libraries(duke3d PRIVATE SDL2_mixer::SDL2_mixer)
endif()

if(WIN32)
    target_link_libraries(duke3d PRIVATE ws2_32)
elseif(UNIX)
    target_link_libraries(duke3d PRIVATE m)
endif()

# Install
include(GNUInstallDirs)
install(TARGETS duke3d RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

# Install DUKE3D.GRP if it exists
if(EXISTS "${CMAKE_SOURCE_DIR}/DUKE3D.GRP")
    install(FILES "${CMAKE_SOURCE_DIR}/DUKE3D.GRP"
            DESTINATION ${CMAKE_INSTALL_DATADIR}/duke3d)
endif()

# Install generated_assets/ if it exists
if(EXISTS "${CMAKE_SOURCE_DIR}/generated_assets")
    install(DIRECTORY "${CMAKE_SOURCE_DIR}/generated_assets"
            DESTINATION ${CMAKE_INSTALL_DATADIR}/duke3d
            FILES_MATCHING
            PATTERN "*.VOC"
            PATTERN "*.WAV"
            PATTERN "*.ART"
            PATTERN "*.MAP")
endif()

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
)

# Force C language for uppercase .C files (GCC treats .C as C++)
set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS} PROPERTIES LANGUAGE C)

# Create executable
add_executable(duke3d ${ENGINE_SRCS} ${GAME_SRCS} ${COMPAT_SRCS})

# Include directories
target_include_directories(duke3d PRIVATE
    ${CMAKE_SOURCE_DIR}/compat
    ${CMAKE_SOURCE_DIR}/SRC
    ${CMAKE_SOURCE_DIR}/source
    ${SDL2_INCLUDE_DIRS}
)

# Compiler-specific flags
if(MSVC)
    target_compile_options(duke3d PRIVATE /W0)
    # Force .C files to be treated as C
    set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
        PROPERTIES COMPILE_FLAGS "/Tc")
else()
    # GCC/Clang: legacy code uses gnu89, compat uses gnu11
    set_source_files_properties(${ENGINE_SRCS} ${GAME_SRCS}
        PROPERTIES COMPILE_FLAGS "-std=gnu89 -w -x c")
    set_source_files_properties(${COMPAT_SRCS}
        PROPERTIES COMPILE_FLAGS "-std=gnu11 -Wall")
    # Fast math for engine rendering (fixed-point safe)
    set_source_files_properties(SRC/ENGINE.C
        PROPERTIES COMPILE_FLAGS "-std=gnu89 -w -x c -ffast-math")
endif()

# ENGINE.C needs the ENGINE define
set_source_files_properties(SRC/ENGINE.C PROPERTIES COMPILE_DEFINITIONS ENGINE)

# Link libraries
target_link_libraries(duke3d PRIVATE ${SDL2_LIBRARIES})

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
install(TARGETS duke3d RUNTIME DESTINATION bin)

#!/usr/bin/env python3
"""Build LaZer B1/G3/C3 and two independent implementation adapters."""
import argparse, difflib, json, os, re, shutil, subprocess, sys, tarfile, zipfile
from pathlib import Path
from revision_common import *

HEXL_SOURCES = ['eltwise/eltwise-mult-mod.cpp','eltwise/eltwise-reduce-mod.cpp',
    'eltwise/eltwise-sub-mod.cpp','eltwise/eltwise-add-mod.cpp','eltwise/eltwise-fma-mod.cpp',
    'eltwise/eltwise-cmp-add.cpp','eltwise/eltwise-cmp-sub-mod.cpp','ntt/ntt-internal.cpp',
    'ntt/ntt-radix-2.cpp','ntt/ntt-radix-4.cpp','number-theory/number-theory.cpp']

ARGO_SOURCES = [
    'arith/arith.c',
    'arith/arith_q/poly_q.c',
    'arith/arith_q/poly_q_vec_d.c',
    'arith/arith_q/poly_q_vec_k.c',
    'arith/arith_q/poly_q_vec_m.c',
    'arith/arith_q/poly_q_mat_d_d.c',
    'arith/arith_q/poly_q_mat_d_k.c',
    'arith/arith_q/poly_q_mat_d_m.c',
    'arith/arith_q/poly_q_sampling.c',
    'arith/arith_qiss/poly_qiss.c',
    'arith/arith_qiss/poly_qiss_vec_d.c',
    'arith/arith_qiss/poly_qiss_vec_k.c',
    'arith/arith_qiss/poly_qiss_vec_l.c',
    'arith/arith_qiss/poly_qiss_vec_256.c',
    'arith/arith_qiss/poly_qiss_vec_256_l.c',
    'arith/arith_qiss/poly_qiss_vec_m2.c',
    'arith/arith_qiss/poly_qiss_mat_k_k.c',
    'arith/arith_qiss/poly_qiss_mat_d_k.c',
    'arith/arith_qiss/poly_qiss_mat_d_m2.c',
    'arith/arith_qiss/poly_qiss_mat_256l_m2.c',
    'arith/arith_qiss/poly_qiss_sampling.c',
    'arith/arith_qshow/poly_qshow.c',
    'arith/arith_qshow/poly_qshow_vec_d.c',
    'arith/arith_qshow/poly_qshow_vec_k.c',
    'arith/arith_qshow/poly_qshow_vec_l.c',
    'arith/arith_qshow/poly_qshow_vec_256.c',
    'arith/arith_qshow/poly_qshow_vec_256_l.c',
    'arith/arith_qshow/poly_qshow_vec_m1.c',
    'arith/arith_qshow/poly_qshow_vec_m2.c',
    'arith/arith_qshow/poly_qshow_mat_k_k.c',
    'arith/arith_qshow/poly_qshow_mat_d_k.c',
    'arith/arith_qshow/poly_qshow_mat_d_m1.c',
    'arith/arith_qshow/poly_qshow_mat_d_m2.c',
    'arith/arith_qshow/poly_qshow_mat_256l_m2.c',
    'arith/arith_qshow/poly_qshow_sampling.c',
    'arith/arith_real/poly_real.c',
    'arith/arith_real/poly_real_vec_2d.c',
    'arith/arith_real/poly_real_mat_2d_2d.c',
    'arith/arith_z/poly_z.c',
    'arith/arith_z/poly_z_vec_d.c',
    'arith/arith_z/poly_z_mat_d_d.c',
    'covariance.c',
    'four_squares.c',
    'fips202.c',
    'random.c',
    'randombytes.c',
    'sep.c',
    'osig.c',
    'osig_prove.c',
    'osig_proof_verify.c',
    'show.c',
    'show_prove.c',
    'show_proof_verify.c',
]

def compile_one(cc, src, obj, flags, includes, env, log):
    execute([cc,*flags,*['-I'+str(x) for x in includes],'-c',src,'-o',obj],obj.parent,log,env)

def copy_base(dst):
    shutil.copytree(ROOT/'base_project',dst)

def dependencies(base, dest, cc, cxx, env, log):
    dest.mkdir(parents=True)
    hdr=dest/'include'; lib=dest/'lib'; hdr.mkdir();lib.mkdir()
    cpu=base/'vendor/cpu_features'
    shutil.copytree(cpu/'include',hdr,dirs_exist_ok=True)
    objects=[]
    for name in ['filesystem','stack_line_reader','string_view','cpuinfo_x86','hwcaps']:
        obj=dest/(name+'.o')
        compile_one(cc,cpu/f'src/{name}.c',obj,
            [*FLAGS,'-fPIC','-DSTACK_LINE_READER_BUFFER_SIZE=1024','-DHAVE_STRONG_GETAUXVAL','-DHAVE_DLFCN_H'],
            [hdr,hdr/'internal'],env,log); objects.append(obj)
    execute(['ar','rcs',lib/'libcpu_features.a',*objects],dest,log,env)
    with zipfile.ZipFile(base/'lazer/third_party/hexl-development.zip') as z: z.extractall(dest)
    h=dest/'hexl-development'
    (h/'hexl/include/hexl/util/defines.hpp').write_text('#pragma once\n#define HEXL_USE_GNU 1\n#define HEXL_UNUSED(x) (void)(x)\n')
    objects=[]
    for i,name in enumerate(HEXL_SOURCES):
        obj=dest/f'hexl_{i}.o'
        compile_one(cxx,h/'hexl'/name,obj,[*FLAGS,'-std=c++17','-fPIC'],
                    [h/'hexl/include',h/'hexl',hdr],env,log); objects.append(obj)
    execute(['ar','rcs',lib/'libhexl.a',*objects],dest,log,env)

def build_lazer(dest, dep, cc, cxx, variant, env, log):
    copy_base(dest)
    execute([sys.executable,'e4_select.py',variant],dest,log,env)
    execute([sys.executable,'verify_baseline.py'],dest,log,env)
    l=dest/'lazer'; fal=l/'third_party/Falcon-impl-20211101'
    if not fal.exists():
        with zipfile.ZipFile(l/'third_party/Falcon-impl-20211101.zip') as z:z.extractall(l/'third_party')
        execute(['patch','-p1','-i',l/'src/falcon.patch'],fal,log,env)
    execute(['make','lazer.h'],l,log,env)
    inc=[fal,l,dep/'include']
    cf=[*FLAGS,'-fPIC','-DNDEBUG','-DFALCON_FPNATIVE','-DFALCON_AVX2','-DFALCON_FMA']
    objects=[]
    for name in FALCON:
        obj=fal/f'{name}_revision.o';compile_one(cc,fal/f'{name}.c',obj,cf,inc,env,log);objects.append(obj)
    for name in ['lazer']:
        obj=l/'src'/f'{name}_revision.o';compile_one(cc,l/'src'/f'{name}.c',obj,cf,inc,env,log);objects.append(obj)
    obj=l/'src/hexl_revision.o'
    compile_one(cxx,l/'src/hexl.cpp',obj,[*FLAGS,'-fPIC','-std=c++17'],
        [l/'src',dep/'hexl-development/hexl/include'],env,log);objects.append(obj)
    hp=l/'third_party/hexl-development/build/hexl/lib';hp.mkdir(parents=True,exist_ok=True)
    shutil.copy2(dep/'lib/libhexl.a',hp/'libhexl.a')
    execute([cxx,'-shared','-Wl,-z,defs','-Wl,-soname,liblazer.so','-o',l/'liblazer.so',
        *objects,dep/'lib/libhexl.a',dep/'lib/libcpu_features.a','-lmpfr','-lgmp','-lm'],dest,log,env)
    execute(['ar','rcs',l/'liblazer.a',*objects],dest,log,env)
    e=env.copy(); e.update(CC=cc,CXX=cxx,CFLAGS=' '.join(FLAGS),CXXFLAGS=' '.join(FLAGS))
    e['LD_LIBRARY_PATH']=str(l)+os.pathsep+e.get('LD_LIBRARY_PATH','')
    execute([sys.executable,'lazer_cffi_build.py','..'],l/'python',log,e)
    execute([sys.executable,'../params_cffi_build.py','anon_cred_params.h','../..'],l/'python/anon_cred',log,e)
    execute([sys.executable,'-c','import anon_cred; print("REV_IMPORT_OK")'],l/'python/anon_cred',log,e)

def build_external(dest, cc, cxx, env, log):
    """Build pqzk-blns supporting PQZK_BLNS, PQZK_BLNS_PADDED, and PQZK_BLNS_COMPACT."""
    shutil.copytree(ROOT/'vendor/pqzk-blns',dest)
    param=dest/'params.h';old=param.read_text();new=old
    replacements={
        '#define lm0     2 //1':'#define lm0     1 // task adapter: eight 64-coefficient attributes',
        '#define l0          16 //8':'#define l0          8 // task adapter',
        '// #define USE_ISSUER_BLIND_SIGNATURE':'#define USE_ISSUER_BLIND_SIGNATURE',
        '#define USE_ISSUER_SIGNATURE        ':'// #define USE_ISSUER_SIGNATURE        '
    }
    for a,b in replacements.items():
        expected=3 if a.startswith('#define lm0') else 1
        if new.count(a)!=expected: raise RuntimeError('external upstream changed: '+a)
        new=new.replace(a,b,1)
    param.write_text(new)
    patch=list(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='params.h.upstream',tofile='params.h'))

    # Hook in Hash.cc: optional input-bit mapping; this does not add binary witness proof constraints
    p_hash = dest/'Hash.cc'; old_hash = p_hash.read_text()
    new_hash = 'bool revision_binary_hm = false;\n' + old_hash
    hm_target = 'void HM(vec_ZZ& m_i, const string& a_i)\n{'
    hm_replacement = (
        'void HM(vec_ZZ& m_i, const string& a_i)\n{\n'
        '    if (revision_binary_hm) {\n'
        '        m_i.SetLength(h0);\n'
        '        for (long k = 0; k < h0; k++) {\n'
        '            unsigned char byte = (k / 8 < (long)a_i.length()) ? (unsigned char)a_i[k / 8] : 0;\n'
        '            m_i[k] = ZZ((byte >> (k % 8)) & 1);\n'
        '        }\n'
        '        return;\n'
        '    }'
    )
    if new_hash.count(hm_target) != 1:
        hm_target_crlf = 'void HM(vec_ZZ& m_i, const string& a_i)\r\n{'
        if new_hash.count(hm_target_crlf) != 1:
            raise RuntimeError('unexpected HM signature in Hash.cc')
        new_hash = new_hash.replace(hm_target_crlf, hm_replacement.replace('\n', '\r\n'), 1)
    else:
        new_hash = new_hash.replace(hm_target, hm_replacement, 1)
    p_hash.write_text(new_hash)
    patch += list(difflib.unified_diff(old_hash.splitlines(True), new_hash.splitlines(True), fromfile='Hash.cc.upstream', tofile='Hash.cc'))

    # Hook in ISIS.cc: capture actual serialized proof length AND allow aux (num_idx_pub) decoupled from l0 - num_idx_hid for PADDED mode
    p=dest/'ISIS.cc';old=p.read_text();new='#include <cstddef>\nsize_t revision_last_proof_bytes = 0;\n'+old
    token='*Pi_ptr = new uint8_t[len_Pi];'
    if new.count(token)!=1:raise RuntimeError('unexpected proof allocation')
    new=new.replace(token,'revision_last_proof_bytes = len_Pi;\n    '+token)
    pub_tok = 'const ulong     num_idx_pub = l0 - num_idx_hid; // number of disclosed attributes (revealed)'
    if new.count(pub_tok) != 2:
        raise RuntimeError('unexpected num_idx_pub line in ISIS.cc')
    new = new.replace(pub_tok, 'const ulong     num_idx_pub = static_cast<ulong>(aux); // decoupled for padded vs compact comparison')
    p.write_text(new)
    patch+=list(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='ISIS.cc.upstream',tofile='ISIS.cc'))

    # Fix upstream double-free in Com.cc
    p=dest/'Com.cc';old=p.read_text();token='delete[] (*Pi_ptr);'
    if old.count(token)!=1:raise RuntimeError('unexpected Com proof ownership')
    new=old.replace(token,'/* Revision: caller owns/frees Pi; avoid double-free in I_VerCred. */')
    p.write_text(new)
    patch+=list(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='Com.cc.upstream',tofile='Com.cc'))
    (dest/'REVISION.diff').write_text(''.join(patch))

    with zipfile.ZipFile(ROOT/'base_project/lazer/third_party/Falcon-impl-20211101.zip') as z:z.extractall(dest)
    fal=dest/'Falcon-impl-20211101';objects=[]
    for name in FALCON:
        obj=fal/f'{name}_revision.o'
        compile_one(cc,fal/f'{name}.c',obj,[*FLAGS,'-fPIC'],[fal],env,log);objects.append(obj)
    for p in sorted(dest.glob('*.cc')):
        if p.name in ['bench.cc','BLNS.cc']:continue
        obj=dest/(p.stem+'_revision.o')
        compile_one(cxx,p,obj,[*FLAGS,'-std=gnu++11','-pthread','-Drestrict=__restrict__','-DENABLE_FALCON'],[dest,fal],env,log);objects.append(obj)
    shutil.copy2(ROOT/'external_worker.cc',dest/'revision_worker.cc')
    obj=dest/'revision_worker.o'
    compile_one(cxx,dest/'revision_worker.cc',obj,[*FLAGS,'-std=gnu++11','-pthread','-Drestrict=__restrict__','-DENABLE_FALCON'],[dest,fal],env,log);objects.append(obj)
    execute([cxx,*FLAGS,'-pthread','-o',dest/'revision_worker',*objects,'-lntl','-lgmp','-lm'],dest,log,env)

def ensure_flint(workspace, cc, env, log, jobs=4):
    """Use system FLINT (>=3.0 with arb.h) if available, otherwise build bundled vendor/flint.tar.gz."""
    sys_inc = Path('/usr/include')
    if os.environ.get('REV_ALLOW_SYSTEM_FLINT')=='1' and (sys_inc/'flint/nmod_poly.h').exists() and (sys_inc/'flint/arb.h').exists():
        for libdir in [Path('/usr/lib/x86_64-linux-gnu'), Path('/usr/lib64'), Path('/usr/lib')]:
            cand = list(libdir.glob('libflint.so*'))
            if cand:
                return sys_inc, cand[0].resolve(), 'SYSTEM_FLINT'
    flint_root = workspace/'flint_build'
    prefix = workspace/'flint_install'
    if (prefix/'lib/libflint.so').exists():
        return prefix/'include', (prefix/'lib/libflint.so').resolve(), 'BUNDLED_FLINT'
    if flint_root.exists(): shutil.rmtree(flint_root)
    flint_root.mkdir(parents=True)
    with tarfile.open(ROOT/'vendor/flint.tar.gz') as tf:
        tf.extractall(flint_root)
    execute(['sh','bootstrap.sh'], flint_root, log, env)
    b_env = env.copy()
    b_env['CC'] = cc
    b_env['CFLAGS'] = ' '.join(FLAGS)
    execute(['./configure', f'--prefix={prefix}', '--enable-avx2', '--disable-avx512', '--disable-pthread', '--disable-static'], flint_root, log, b_env)
    execute(['make', f'-j{jobs}'], flint_root, log, b_env)
    execute(['make', 'install'], flint_root, log, b_env)
    return prefix/'include', (prefix/'lib/libflint.so').resolve(), 'BUNDLED_FLINT'

def patch_and_build_argo_variant(dest, cc, flint_inc, flint_so, variant_name, param_m, param_m_hid, param_m1_show, env, log):
    """Extract vendor/argo.tar.gz, apply selective disclosure + dimension adaptation, and compile worker."""
    if dest.exists(): shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(ROOT/'vendor/argo.tar.gz') as tf:
        tf.extractall(dest)
    code = dest/'code'

    # 1. Patch include/params.h
    p_params = code/'include/params.h'
    old_p = p_params.read_text()
    new_p = old_p
    param_m1_k_iss = 16 + param_m
    param_m1_iss = 4 * param_m1_k_iss
    new_p = re.sub(r'^#define\s+PARAM_M\s+\d+', f'#define PARAM_M {param_m}\n#define PARAM_M_SHOW_HID {param_m_hid}', new_p, count=1, flags=re.M)
    new_p = re.sub(r'^#define\s+PARAM_M1_ISS\s+\d+', f'#define PARAM_M1_ISS {param_m1_iss}', new_p, count=1, flags=re.M)
    new_p = re.sub(r'^#define\s+PARAM_M1_K_ISS\s+\d+', f'#define PARAM_M1_K_ISS {param_m1_k_iss}', new_p, count=1, flags=re.M)
    new_p = re.sub(r'^#define\s+PARAM_M1_SHOW\s+\d+', f'#define PARAM_M1_SHOW {param_m1_show}', new_p, count=1, flags=re.M)
    p_params.write_text(new_p)

    # 2. Patch include/show.h
    p_show_h = code/'include/show.h'
    old_sh = p_show_h.read_text()
    new_sh = old_sh.replace('D_embed[PARAM_D][PARAM_M]', 'D_embed[PARAM_D][PARAM_M_SHOW_HID]')
    p_show_h.write_text(new_sh)

    # 3. Patch src/show.c for selective disclosure D={0,4,5}
    p_show_c = code/'src/show.c'
    old_sc = p_show_c.read_text()
    new_sc = old_sc.replace('D_embed[PARAM_D][PARAM_M]', 'D_embed[PARAM_D][PARAM_M_SHOW_HID]')

    orig_u_block = "\n".join([
        "  // embedding u (u_embed = theta(q1.u))",
        "  for (i = 0; i < PARAM_D; i++) {",
        "    poly_qshow_subring_embed_vec_k(u_embed[i], u->entries[i], PARAM_Q1_SHOW);",
        "  }",
        "",
        "  // recovering v_11 = u + Ds.usk + D.m - A'.v12 - (tG - B).v2 - A3.v3",
        "  // storing message as polynomial vector",
        "  for (i = 0; i < PARAM_M; i++) {",
        "    poly_q_from_bits(m->entries[i], &msg[i * PARAM_N/8]);",
        "  }",
        "  poly_q_mat_d_m_mul_vec_m(v11, D, m);",
        "  poly_q_vec_d_add(v11, v11, u); // u can be used as a temp variable now",
    ])

    new_u_block = "\n".join([
        "  // storing message as polynomial vector",
        "  for (i = 0; i < PARAM_M; i++) {",
        "    poly_q_from_bits(m->entries[i], &msg[i * PARAM_N/8]);",
        "  }",
        "  // recovering v_11 = u + Ds.usk + D.m - A'.v12 - (tG - B).v2 - A3.v3",
        "  poly_q_mat_d_m_mul_vec_m(v11, D, m);",
        "  poly_q_vec_d_add(v11, v11, u);",
        "#if PARAM_M == 8",
        "  {",
        "    const size_t disc_idx[3] = {0, 4, 5};",
        "    for (size_t d_i = 0; d_i < 3; d_i++) {",
        "      size_t col = disc_idx[d_i];",
        "      for (i = 0; i < PARAM_D; i++) {",
        "        poly_q_mul(tmp_poly, D->rows[i]->entries[col], m->entries[col]);",
        "        poly_q_add(u->entries[i], u->entries[i], tmp_poly);",
        "      }",
        "    }",
        "  }",
        "#endif",
        "  // embedding u (u_embed = theta(q1.u_disc))",
        "  for (i = 0; i < PARAM_D; i++) {",
        "    poly_qshow_subring_embed_vec_k(u_embed[i], u->entries[i], PARAM_Q1_SHOW);",
        "  }",
    ])
    if orig_u_block not in new_sc:
        raise RuntimeError('unexpected u_embed block in Argo show.c')
    new_sc = new_sc.replace(orig_u_block, new_u_block, 1)

    orig_msg_embed = "\n".join([
        "  // msg",
        "  for (i = 0; i < PARAM_M; i++) {",
        "    poly_qshow_subring_embed_vec_k(tmp_vec_k, m->entries[i], 1);",
        "    for (j = 0; j < PARAM_K_SHOW; j++) {",
        "      poly_qshow_set(s1->entries[IDX_M_SHOW + i*PARAM_K_SHOW + j], tmp_vec_k->entries[j]);",
        "    }",
        "  }",
    ])
    new_msg_embed = "\n".join([
        "  // msg (selective disclosure: Native 10, Padded 8 with {0,4,5} zeroed, or Compact 5 hidden {1,2,3,6,7})",
        "#if PARAM_M == 10",
        "  for (i = 0; i < PARAM_M; i++) {",
        "    poly_qshow_subring_embed_vec_k(tmp_vec_k, m->entries[i], 1);",
        "    for (j = 0; j < PARAM_K_SHOW; j++) {",
        "      poly_qshow_set(s1->entries[IDX_M_SHOW + i*PARAM_K_SHOW + j], tmp_vec_k->entries[j]);",
        "    }",
        "  }",
        "#elif PARAM_M_SHOW_HID == 8",
        "  for (i = 0; i < PARAM_M; i++) {",
        "    if (i == 0 || i == 4 || i == 5) {",
        "      for (j = 0; j < PARAM_K_SHOW; j++) {",
        "        poly_qshow_zero(s1->entries[IDX_M_SHOW + i*PARAM_K_SHOW + j]);",
        "      }",
        "    } else {",
        "      poly_qshow_subring_embed_vec_k(tmp_vec_k, m->entries[i], 1);",
        "      for (j = 0; j < PARAM_K_SHOW; j++) {",
        "        poly_qshow_set(s1->entries[IDX_M_SHOW + i*PARAM_K_SHOW + j], tmp_vec_k->entries[j]);",
        "      }",
        "    }",
        "  }",
        "#else",
        "  {",
        "    const size_t hid_idx[5] = {1, 2, 3, 6, 7};",
        "    for (i = 0; i < 5; i++) {",
        "      poly_qshow_subring_embed_vec_k(tmp_vec_k, m->entries[hid_idx[i]], 1);",
        "      for (j = 0; j < PARAM_K_SHOW; j++) {",
        "        poly_qshow_set(s1->entries[IDX_M_SHOW + i*PARAM_K_SHOW + j], tmp_vec_k->entries[j]);",
        "      }",
        "    }",
        "  }",
        "#endif",
    ])
    if orig_msg_embed not in new_sc:
        raise RuntimeError('unexpected msg embed block in Argo show.c')
    new_sc = new_sc.replace(orig_msg_embed, new_msg_embed, 1)

    orig_d_embed = "\n".join([
        "    for (j = 0; j < PARAM_M; j++) {",
        "      poly_qshow_subring_embed_mat_k_k(D_embed[i][j], D->rows[i]->entries[j], PARAM_Q1_SHOW); // D",
        "    }",
    ])
    new_d_embed = "\n".join([
        "#if PARAM_M == 10",
        "    for (j = 0; j < PARAM_M; j++) {",
        "      poly_qshow_subring_embed_mat_k_k(D_embed[i][j], D->rows[i]->entries[j], PARAM_Q1_SHOW);",
        "    }",
        "#elif PARAM_M_SHOW_HID == 8",
        "    for (j = 0; j < PARAM_M; j++) {",
        "      if (j == 0 || j == 4 || j == 5) {",
        "        poly_qshow_mat_k_k_zero(D_embed[i][j]);",
        "      } else {",
        "        poly_qshow_subring_embed_mat_k_k(D_embed[i][j], D->rows[i]->entries[j], PARAM_Q1_SHOW);",
        "      }",
        "    }",
        "#else",
        "    {",
        "      const size_t hid_idx[5] = {1, 2, 3, 6, 7};",
        "      for (j = 0; j < 5; j++) {",
        "        poly_qshow_subring_embed_mat_k_k(D_embed[i][j], D->rows[i]->entries[hid_idx[j]], PARAM_Q1_SHOW);",
        "      }",
        "    }",
        "#endif",
    ])
    if orig_d_embed not in new_sc:
        raise RuntimeError('unexpected D_embed block in Argo show.c')
    new_sc = new_sc.replace(orig_d_embed, new_d_embed, 1)
    p_show_c.write_text(new_sc)

    # 4. Patch src/show_prove.c (record attempts K and use PARAM_M_SHOW_HID)
    p_sp = code/'src/show_prove.c'
    old_sp = p_sp.read_text()
    new_sp = 'long argo_last_attempts = 0;\n' + old_sp
    new_sp = new_sp.replace('D_embed[PARAM_D][PARAM_M]', 'D_embed[PARAM_D][PARAM_M_SHOW_HID]')
    new_sp = new_sp.replace('for (j = 0; j < PARAM_M*PARAM_K_SHOW; j++)', 'for (j = 0; j < PARAM_M_SHOW_HID*PARAM_K_SHOW; j++)')
    new_sp = new_sp.replace('  kappa = 0;\nreject:', '  kappa = 0;\n  argo_last_attempts = 0;\nreject:\n  argo_last_attempts++;')
    p_sp.write_text(new_sp)

    # 5. Patch src/show_proof_verify.c
    p_sv = code/'src/show_proof_verify.c'
    old_sv = p_sv.read_text()
    new_sv = old_sv.replace('D_embed[PARAM_D][PARAM_M]', 'D_embed[PARAM_D][PARAM_M_SHOW_HID]')
    new_sv = new_sv.replace('for (j = 0; j < PARAM_M*PARAM_K_SHOW; j++)', 'for (j = 0; j < PARAM_M_SHOW_HID*PARAM_K_SHOW; j++)')
    p_sv.write_text(new_sv)

    inc_dirs = [
        code/'include',
        code/'include/arith',
        code/'include/arith/arith_q',
        code/'include/arith/arith_qiss',
        code/'include/arith/arith_qshow',
        code/'include/arith/arith_real',
        code/'include/arith/arith_z',
        flint_inc,
    ]
    c_flags = [*FLAGS, '-std=gnu11', '-D_GNU_SOURCE', '-DREMOVE_ASSERTS=1', f'-DARGO_VARIANT_NAME="{variant_name}"']
    objs = []
    obj_dir = dest/'objs'
    obj_dir.mkdir()
    for idx, rel_src in enumerate(ARGO_SOURCES):
        obj = obj_dir/f'argo_{idx:02d}.o'
        compile_one(cc, code/'src'/rel_src, obj, c_flags, inc_dirs, env, log)
        objs.append(obj)
    for name in ['argo_worker.c','argo_wire.h','argo_public.h']:
        shutil.copy2(ROOT/name, dest/name)
    w_obj = obj_dir/'argo_worker.o'
    compile_one(cc, dest/'argo_worker.c', w_obj, c_flags, inc_dirs, env, log)
    objs.append(w_obj)
    execute([cc, *FLAGS, f'-Wl,-rpath,{flint_so.parent}', '-o', dest/'argo_worker', *objs, str(flint_so), '-lmpfr', '-lgmp', '-lm'], dest, log, env)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--compilers',nargs='+',choices=['gcc','clang'],default=['gcc','clang'])
    p.add_argument('--external',action='store_true',help='Build pqzk-blns (enabled by default unless --without-external)')
    p.add_argument('--with-argo',action='store_true',help='Build Argo (ARGO_NATIVE, ARGO_PADDED, ARGO_COMPACT)')
    p.add_argument('--all-baselines',action='store_true',help='Build both external implementations: pqzk-blns and Argo')
    p.add_argument('--jobs',type=int,default=4)
    a=p.parse_args()
    if a.all_baselines:
        a.external = True
        a.with_argo = True
    w=a.workspace.resolve();w.mkdir(parents=True,exist_ok=True)
    env=clean_env(); compiler_map={}
    for label in a.compilers:
        cc=shutil.which(os.environ.get('REV_'+label.upper()+'_CC',label))
        cxx=shutil.which(os.environ.get('REV_'+label.upper()+'_CXX','g++' if label=='gcc' else 'clang++'))
        if not cc or not cxx:raise SystemExit('Missing '+label+' compiler; see README')
        compiler_map[label]=(str(Path(cc).absolute()),str(Path(cxx).absolute()))
    spec=dict(schema='LAZER-TWO-BASELINES-1',python=sys.executable,python_version=sys.version,
        source=manifest(ROOT/'base_project'),driver={name:sha(ROOT/name) for name in ['build_revision.py','revision_common.py','argo_wire.h','argo_public.h']},
        external_sources=manifest(ROOT/'vendor/pqzk-blns'),external_worker_sha=sha(ROOT/'external_worker.cc'),
        argo_worker_sha=sha(ROOT/'argo_worker.c'),vendor_archives={x:sha(ROOT/'vendor'/x) for x in ['argo.tar.gz','flint.tar.gz']},
        flags=FLAGS,compilers={k:tool_info(*v) for k,v in compiler_map.items()},
        external=a.external,with_argo=a.with_argo)
    cfg=w/'build_config.json'
    if cfg.exists() and json.loads(cfg.read_text())!=spec:raise SystemExit('Build configuration changed; choose NEW workspace')
    dump(cfg,spec)
    for label,(cc,cxx) in compiler_map.items():
        d=w/label;d.mkdir(exist_ok=True);dep=d/'dependencies'
        if not (dep/'COMPLETE.json').exists():
            if dep.exists():shutil.rmtree(dep)
            print('BUILD dependencies',label,flush=True)
            dependencies(ROOT/'base_project',dep,cc,cxx,env,w/'logs'/f'{label}_deps.log')
            dump(dep/'COMPLETE.json',manifest(dep))
        for v in ['B1','G3','C3']:
            dst=d/v
            if not (dst/'BUILD_COMPLETE.json').exists():
                if dst.exists():shutil.rmtree(dst)
                print('BUILD',label,v,flush=True)
                build_lazer(dst,dep,cc,cxx,v,env,w/'logs'/f'{label}_{v}.log')
                files={str(x.relative_to(dst)):sha(x) for x in dst.rglob('*') if x.is_file()
                    and (x.suffix=='.so' or x.name in ['anon_cred.py','anon_cred_params.h','lazer.h','ACTIVE_VARIANT.json'])}
                dump(dst/'BUILD_COMPLETE.json',dict(compiler=label,variant=v,files=files))
        if a.external and label=='gcc':
            dst=d/'external'
            if not (dst/'BUILD_COMPLETE.json').exists():
                if dst.exists():shutil.rmtree(dst)
                print('BUILD external (pqzk-blns: Native + Binary Padded + Binary Compact)',label,flush=True)
                build_external(dst,cc,cxx,env,w/'logs'/f'{label}_external.log')
                dump(dst/'BUILD_COMPLETE.json',dict(compiler=label,commit=UPSTREAM_COMMIT,
                    files={str(x.relative_to(dst)):sha(x) for x in dst.iterdir() if x.is_file() and x.name in ['revision_worker','params.h','ISIS.cc','Com.cc','Hash.cc','REVISION.diff']}))
        if a.with_argo and label=='gcc':
            flint_inc, flint_so, flint_mode = ensure_flint(w, cc, env, w/'logs'/f'{label}_flint.log', jobs=a.jobs)
            for vname, pm, pm_hid, pm1 in [
                ('ARGO_NATIVE', 10, 10, 211),
                ('ARGO_PADDED', 8, 8, 203),
                ('ARGO_COMPACT', 8, 5, 191),
            ]:
                dst = d/vname
                if not (dst/'BUILD_COMPLETE.json').exists():
                    print('BUILD Argo', label, vname, f'(m={pm}, m_hid={pm_hid}, m1={pm1})', flush=True)
                    patch_and_build_argo_variant(dst, cc, flint_inc, flint_so, vname, pm, pm_hid, pm1, env, w/'logs'/f'{label}_{vname}.log')
                    dump(dst/'BUILD_COMPLETE.json', dict(
                        compiler=label, variant=vname, flint_mode=flint_mode,
                        files={x:sha(dst/x) for x in ['argo_worker','argo_worker.c','argo_wire.h','argo_public.h','code/include/params.h']},flint_library_sha256=sha(flint_so)
                    ))
    print('BUILD COMPLETE',w,flush=True)

if __name__=='__main__':main()

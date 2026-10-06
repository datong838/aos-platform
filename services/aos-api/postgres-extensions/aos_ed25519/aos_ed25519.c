/* Pure verification only. Trust/purpose/currentness belong to the caller. */
#include "postgres.h"
#include "fmgr.h"
#include "varatt.h"
#include "access/detoast.h"
#include <openssl/evp.h>

PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(aos_ed25519_verify);

#define AOS_MESSAGE_LIMIT (2 * 1024 * 1024)

Datum
aos_ed25519_verify(PG_FUNCTION_ARGS)
{
    Size message_size = toast_raw_datum_size(PG_GETARG_DATUM(1));
    bytea *signature;
    bytea *message;
    bytea *public_key;
    EVP_PKEY *key;
    EVP_MD_CTX *context;
    bool valid = false;

    /* Check logical lengths before allocating any decompressed input. */
    if (toast_raw_datum_size(PG_GETARG_DATUM(0)) != VARHDRSZ + 64 ||
        toast_raw_datum_size(PG_GETARG_DATUM(2)) != VARHDRSZ + 32 ||
        message_size < VARHDRSZ || message_size > VARHDRSZ + AOS_MESSAGE_LIMIT)
        PG_RETURN_BOOL(false);

    /* PostgreSQL ERROR/longjmp can occur here, before any EVP allocation. */
    signature = PG_GETARG_BYTEA_PP(0);
    message = PG_GETARG_BYTEA_PP(1);
    public_key = PG_GETARG_BYTEA_PP(2);

    /* No PG API/ERROR/interrupt between these allocations and their frees. */
    key = EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519, NULL,
                                    (unsigned char *) VARDATA_ANY(public_key), 32);
    context = EVP_MD_CTX_new();
    if (key != NULL && context != NULL &&
        EVP_DigestVerifyInit(context, NULL, NULL, NULL, key) == 1)
        valid = EVP_DigestVerify(context,
                                (unsigned char *) VARDATA_ANY(signature), 64,
                                (unsigned char *) VARDATA_ANY(message),
                                VARSIZE_ANY_EXHDR(message)) == 1;
    EVP_MD_CTX_free(context);
    EVP_PKEY_free(key);

    PG_FREE_IF_COPY(signature, 0);
    PG_FREE_IF_COPY(message, 1);
    PG_FREE_IF_COPY(public_key, 2);
    PG_RETURN_BOOL(valid);
}

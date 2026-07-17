/**
 * INTENTIONAL G3 FIXTURE — must make check-no-upstream-sdk.ps1 -ExpectFail pass.
 * Not imported by the app. Delete only after CI wires a permanent fixture path.
 */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-nocheck
import openai from "openai";
void openai;

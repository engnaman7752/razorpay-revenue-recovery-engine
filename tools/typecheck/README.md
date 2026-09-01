# Offline type-check for the backend

`mvn` needs Maven Central. When that is unreachable (restricted network, or a
quick check without a full build), these hand-written API stubs let `javac`
type-check every line of `backend/src` on its own.

They are **only** for compile checking — no behaviour, never packaged, never on
the runtime classpath. `mvn package` remains the real build.

```bash
bash tools/typecheck/run.sh
```

Catches: wrong types, bad signatures, null-to-primitive, missing methods,
unreachable code. Does not catch: Spring wiring, SQL, or anything at runtime.
If you add a Spring/Jackson/JPA API the stubs don't cover yet, javac says
"cannot find symbol" — add that one method to the matching stub file.

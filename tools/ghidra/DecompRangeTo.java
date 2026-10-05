import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.io.*;

// args: outfile startAddr endAddr -> decompile every function whose entry is in [start,end)
public class DecompRangeTo extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        Address s = sp.getAddress(new java.math.BigInteger(a[1].replace("0x",""),16).longValue());
        Address e = sp.getAddress(new java.math.BigInteger(a[2].replace("0x",""),16).longValue());
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(new FileWriter(a[0]))) {
            FunctionIterator it = currentProgram.getFunctionManager().getFunctions(new AddressSet(s, e), true);
            while (it.hasNext()) {
                Function f = it.next();
                DecompileResults r = d.decompileFunction(f, 60, monitor);
                w.println("\n// === " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses());
                if (r.decompileCompleted()) w.println(r.getDecompiledFunction().getC());
            }
        }
    }
}

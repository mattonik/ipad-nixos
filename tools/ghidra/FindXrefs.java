import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.Function;

public class FindXrefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (String a : getScriptArgs()) {
            Address ad = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(new java.math.BigInteger(a.replace("0x",""),16).longValue());
            println("=== xrefs to " + a);
            ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(ad);
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
                println("  from " + r.getFromAddress() + " in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "???"));
            }
        }
    }
}

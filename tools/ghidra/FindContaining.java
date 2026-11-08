import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
public class FindContaining extends GhidraScript {
 public void run() throws Exception {
  AddressSpace s=currentProgram.getAddressFactory().getDefaultAddressSpace();
  for(String arg:getScriptArgs()) {Address a=s.getAddress(new java.math.BigInteger(arg,16).longValue()); Function f=getFunctionContaining(a); println(a+" in "+(f==null?"none":f.getEntryPoint()));}
 }
}
